"""
3D Model Converter and Downloader

This module handles downloading and converting 3D models for components
Based on easyeda2kicad implementation
"""
from typing import Dict, Any, Optional
from pathlib import Path
import json
import re
import textwrap
import requests
from ..utils.logger import get_logger
from ..api.lcsc_api import get_api_client

logger = get_logger()

# EasyEDA 3D model endpoints (from easyeda2kicad)
ENDPOINT_3D_MODEL_OBJ = "https://modules.easyeda.com/3dmodel/{uuid}"
ENDPOINT_3D_MODEL_STEP = "https://modules.easyeda.com/qAxj6KHrDKw4blvCG8QJPs7Y/{uuid}"


class Model3DConverter:
    """Converter and downloader for 3D models"""

    def __init__(self):
        """Initialize 3D model converter"""
        self.logger = get_logger("model_3d_converter")
        self.api_client = get_api_client()

    def download_model(
        self,
        model_url: str,
        output_path: Path,
        model_format: str = "step"
    ) -> bool:
        """
        Download 3D model from URL

        Args:
            model_url: URL to 3D model file
            output_path: Local path to save model
            model_format: Model format (step, wrl, etc.)

        Returns:
            True if successful

        Raises:
            IOError: If download fails
        """
        self.logger.info(f"Downloading 3D model: {model_url}")

        try:
            # Ensure correct extension
            if not output_path.suffix:
                output_path = output_path.with_suffix(f".{model_format}")

            # Download using API client
            success = self.api_client.download_file(model_url, output_path)

            if success:
                self.logger.info(f"3D model downloaded: {output_path}")
                return True
            else:
                self.logger.error(f"Failed to download 3D model")
                return False

        except Exception as e:
            self.logger.error(f"3D model download failed: {e}", exc_info=True)
            raise IOError(f"Failed to download 3D model: {e}")

    def convert_model(
        self,
        input_path: Path,
        output_format: str = "step"
    ) -> Optional[Path]:
        """
        Convert 3D model to different format

        Args:
            input_path: Path to input model file
            output_format: Desired output format (step, wrl)

        Returns:
            Path to converted model or None if conversion not needed/failed

        Note:
            Full 3D model conversion requires external tools (e.g., FreeCAD)
            For now, this is a placeholder that will be implemented later
        """
        self.logger.info(f"Converting 3D model: {input_path} -> {output_format}")

        try:
            # Check if conversion is needed
            if input_path.suffix.lower().lstrip('.') == output_format.lower():
                self.logger.info("No conversion needed")
                return input_path

            # TODO: Implement actual conversion
            # This would require:
            # 1. FreeCAD Python API for STEP/VRML conversion
            # 2. Or external tool invocation
            # 3. Or format-specific conversion libraries

            self.logger.warning("3D model conversion not yet implemented")
            return None

        except Exception as e:
            self.logger.error(f"3D model conversion failed: {e}", exc_info=True)
            return None

    def process_component_model(
        self,
        easyeda_data: Dict[str, Any],
        component_info: Dict[str, Any],
        output_dir: Path
    ) -> Dict[str, Path]:
        """
        Process and download all available 3D models for a component

        Downloads OBJ and STEP formats from EasyEDA, converts OBJ to WRL

        Args:
            easyeda_data: EasyEDA component data
            component_info: Component metadata
            output_dir: Directory to save models

        Returns:
            Dictionary mapping format to file path (wrl, step)

        Raises:
            IOError: If processing fails
        """
        self.logger.info(f"Processing 3D models for: {component_info.get('lcsc_id')}")

        models = {}

        try:
            output_dir.mkdir(parents=True, exist_ok=True)

            lcsc_id = component_info.get("lcsc_id", "unknown")

            # Extract 3D model URLs from EasyEDA data
            model_urls = self._extract_model_urls(easyeda_data)

            if not model_urls:
                self.logger.warning("No 3D model URLs found")
                return models

            # Download OBJ file (needed for WRL conversion)
            obj_content = None
            if "obj" in model_urls:
                try:
                    obj_content = self._download_obj(model_urls["obj"])
                    if obj_content:
                        self.logger.info("Downloaded OBJ model successfully")
                except Exception as e:
                    self.logger.warning(f"Failed to download OBJ model: {e}")

            # Download STEP file
            if "step" in model_urls:
                step_path = output_dir / f"{lcsc_id}.step"
                try:
                    step_content = self._download_step(model_urls["step"])
                    if step_content:
                        with open(step_path, 'wb') as f:
                            f.write(step_content)
                        models["step"] = step_path
                        self.logger.info(f"STEP model saved: {step_path}")
                except Exception as e:
                    self.logger.warning(f"Failed to download STEP model: {e}")

            # Convert OBJ to WRL
            if obj_content:
                wrl_path = output_dir / f"{lcsc_id}.wrl"
                try:
                    wrl_content = self._convert_obj_to_wrl(obj_content)
                    if wrl_content:
                        with open(wrl_path, 'w', encoding='utf-8') as f:
                            f.write(wrl_content)
                        models["wrl"] = wrl_path
                        self.logger.info(f"WRL model saved: {wrl_path}")
                except Exception as e:
                    self.logger.warning(f"Failed to convert OBJ to WRL: {e}")

            if not models:
                self.logger.warning("No 3D models downloaded successfully")

            return models

        except Exception as e:
            self.logger.error(f"3D model processing failed: {e}", exc_info=True)
            raise IOError(f"Failed to process 3D models: {e}")

    def _extract_3d_model_uuid(self, easyeda_data: Dict[str, Any]) -> Optional[str]:
        """
        Extract 3D model UUID from EasyEDA packageDetail data

        The UUID is stored in a SVGNODE element within the shape array

        Args:
            easyeda_data: EasyEDA component data

        Returns:
            UUID string or None if not found
        """
        try:
            # Navigate to packageDetail.dataStr.shape
            if "packageDetail" not in easyeda_data:
                self.logger.debug("No packageDetail in EasyEDA data")
                return None

            package_detail = easyeda_data["packageDetail"]
            if "dataStr" not in package_detail:
                self.logger.debug("No dataStr in packageDetail")
                return None

            data_str = package_detail["dataStr"]
            if "shape" not in data_str:
                self.logger.debug("No shape in dataStr")
                return None

            shape_array = data_str["shape"]

            # Find SVGNODE element containing 3D model info
            for line in shape_array:
                if not isinstance(line, str):
                    continue

                parts = line.split("~")
                if len(parts) < 2:
                    continue

                designator = parts[0]
                if designator == "SVGNODE":
                    # Parse JSON from second part
                    try:
                        raw_json = parts[1]
                        svg_data = json.loads(raw_json)

                        # Extract UUID from attrs
                        if "attrs" in svg_data and "uuid" in svg_data["attrs"]:
                            uuid = svg_data["attrs"]["uuid"]
                            self.logger.info(f"Found 3D model UUID: {uuid}")
                            return uuid
                    except json.JSONDecodeError as e:
                        self.logger.warning(f"Failed to parse SVGNODE JSON: {e}")
                        continue

            self.logger.debug("No SVGNODE with 3D model UUID found")
            return None

        except Exception as e:
            self.logger.error(f"Error extracting 3D model UUID: {e}", exc_info=True)
            return None

    def _extract_model_urls(self, easyeda_data: Dict[str, Any]) -> Dict[str, str]:
        """
        Extract 3D model URLs from EasyEDA data

        Args:
            easyeda_data: EasyEDA component data

        Returns:
            Dictionary mapping format to URL
        """
        model_urls = {}

        # Extract UUID from SVGNODE
        uuid = self._extract_3d_model_uuid(easyeda_data)

        if uuid:
            # Build URLs using the UUID
            model_urls["obj"] = ENDPOINT_3D_MODEL_OBJ.format(uuid=uuid)
            model_urls["step"] = ENDPOINT_3D_MODEL_STEP.format(uuid=uuid)
            self.logger.info(f"Generated 3D model URLs from UUID: {uuid}")
        else:
            self.logger.warning("No 3D model UUID found in EasyEDA data")

        return model_urls

    def _download_obj(self, url: str) -> Optional[str]:
        """
        Download OBJ file from EasyEDA

        Args:
            url: URL to OBJ file

        Returns:
            OBJ file content as string, or None if failed
        """
        try:
            self.logger.info(f"Downloading OBJ from: {url}")
            response = requests.get(
                url,
                headers={"User-Agent": "kicad-lcsc-manager"},
                timeout=30
            )

            if response.status_code == 200:
                return response.content.decode('utf-8')
            else:
                self.logger.error(f"Failed to download OBJ: HTTP {response.status_code}")
                return None

        except Exception as e:
            self.logger.error(f"Error downloading OBJ: {e}")
            return None

    def _download_step(self, url: str) -> Optional[bytes]:
        """
        Download STEP file from EasyEDA

        Args:
            url: URL to STEP file

        Returns:
            STEP file content as bytes, or None if failed
        """
        try:
            self.logger.info(f"Downloading STEP from: {url}")
            response = requests.get(
                url,
                headers={"User-Agent": "kicad-lcsc-manager"},
                timeout=30
            )

            if response.status_code == 200:
                return response.content
            else:
                self.logger.error(f"Failed to download STEP: HTTP {response.status_code}")
                return None

        except Exception as e:
            self.logger.error(f"Error downloading STEP: {e}")
            return None

    def _convert_obj_to_wrl(self, obj_content: str) -> Optional[str]:
        """
        Convert OBJ format to WRL (VRML) format

        Based on easyeda2kicad implementation

        Args:
            obj_content: OBJ file content as string

        Returns:
            WRL file content as string, or None if failed
        """
        try:
            self.logger.info("Converting OBJ to WRL")

            # Extract materials from OBJ
            materials = self._extract_obj_materials(obj_content)

            # Extract vertices from OBJ
            vertices = self._extract_obj_vertices(obj_content)

            # Build WRL content
            wrl_header = """#VRML V2.0 utf8
# 3D model generated by kicad-lcsc-manager
# Based on easyeda2kicad.py
"""

            wrl_content = wrl_header

            # Split OBJ by material usage
            shapes = obj_content.split("usemtl")[1:]

            for shape in shapes:
                lines = shape.splitlines()
                if not lines:
                    continue

                # Get material name (first line)
                material_name = lines[0].strip()

                if material_name not in materials:
                    self.logger.warning(f"Material not found: {material_name}")
                    continue

                material = materials[material_name]

                # Build vertex index mapping
                index_counter = 0
                link_dict = {}
                coord_index = []
                points = []

                # Parse faces (lines starting with 'f ')
                for line in lines[1:]:
                    if len(line) > 0 and line.startswith('f '):
                        # Parse face indices
                        face_parts = line.replace("//", "").split(" ")[1:]
                        face = [int(idx) for idx in face_parts if idx.strip()]

                        face_index = []
                        for index in face:
                            if index not in link_dict:
                                link_dict[index] = index_counter
                                face_index.append(str(index_counter))
                                points.append(vertices[index - 1])
                                index_counter += 1
                            else:
                                face_index.append(str(link_dict[index]))

                        face_index.append("-1")
                        coord_index.append(",".join(face_index) + ",")

                if not points:
                    continue

                # Duplicate last point (as done in easyeda2kicad)
                points.insert(-1, points[-1])

                # Get material colors with defaults
                diffuse_color = " ".join(material.get("diffuse_color", ["0.8", "0.8", "0.8"]))
                specular_color = " ".join(material.get("specular_color", ["0.5", "0.5", "0.5"]))

                # Build VRML shape
                shape_str = textwrap.dedent(
                    f"""
            Shape{{
                appearance Appearance {{
                    material  Material 	{{
                        diffuseColor {diffuse_color}
                        specularColor {specular_color}
                        ambientIntensity 0.2
                        transparency 0
                        shininess 0.5
                    }}
                }}
                geometry IndexedFaceSet {{
                    ccw TRUE
                    solid FALSE
                    coord DEF co Coordinate {{
                        point [
                            {(", ").join(points)}
                        ]
                    }}
                    coordIndex [
                        {"".join(coord_index)}
                    ]
                }}
            }}"""
                )

                wrl_content += shape_str

            return wrl_content

        except Exception as e:
            self.logger.error(f"Error converting OBJ to WRL: {e}", exc_info=True)
            return None

    def _extract_obj_materials(self, obj_content: str) -> Dict[str, Dict[str, Any]]:
        """
        Extract material definitions from OBJ content

        Args:
            obj_content: OBJ file content

        Returns:
            Dictionary of material properties
        """
        material_regex = "newmtl .*?endmtl"
        matches = re.findall(pattern=material_regex, string=obj_content, flags=re.DOTALL)

        materials = {}
        for match in matches:
            material = {}
            for value in match.splitlines():
                if value.startswith("newmtl"):
                    material_id = value.split(" ")[1]
                elif value.startswith("Ka"):
                    material["ambient_color"] = value.split(" ")[1:]
                elif value.startswith("Kd"):
                    material["diffuse_color"] = value.split(" ")[1:]
                elif value.startswith("Ks"):
                    material["specular_color"] = value.split(" ")[1:]
                elif value.startswith("d"):
                    material["transparency"] = value.split(" ")[1]

            materials[material_id] = material

        return materials

    def _extract_obj_vertices(self, obj_content: str) -> list:
        """
        Extract vertices from OBJ content and convert to mm

        Args:
            obj_content: OBJ file content

        Returns:
            List of vertex strings in WRL format
        """
        vertices_regex = "v (.*?)\n"
        matches = re.findall(pattern=vertices_regex, string=obj_content, flags=re.DOTALL)

        # Convert from EasyEDA units to mm (divide by 2.54)
        return [
            " ".join([str(round(float(coord) / 2.54, 4)) for coord in vertex.split(" ")])
            for vertex in matches
        ]

    def create_placeholder_model(
        self,
        output_path: Path,
        package_name: str
    ) -> bool:
        """
        Create a placeholder 3D model file

        This creates a simple VRML file as a placeholder when no 3D model is available

        Args:
            output_path: Path to save placeholder model
            package_name: Package name for reference

        Returns:
            True if successful
        """
        self.logger.info(f"Creating placeholder model: {output_path}")

        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)

            # Create simple VRML placeholder
            vrml_content = f'''#VRML V2.0 utf8
# Placeholder 3D model for {package_name}
# Generated by KiCad LCSC Manager

Shape {{
  appearance Appearance {{
    material Material {{
      diffuseColor 0.8 0.8 0.8
      specularColor 0.5 0.5 0.5
      shininess 0.5
    }}
  }}
  geometry Box {{
    size 2 1 0.5
  }}
}}
'''

            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(vrml_content)

            self.logger.info(f"Placeholder model created: {output_path}")
            return True

        except Exception as e:
            self.logger.error(f"Failed to create placeholder model: {e}")
            return False
