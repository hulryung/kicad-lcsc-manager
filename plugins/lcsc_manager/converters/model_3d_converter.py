"""
3D Model Converter and Downloader

This module handles downloading and converting 3D models for components
Based on easyeda2kicad implementation
"""
from typing import Dict, Any, Optional, Tuple, List
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

            # Extract full 3D model info (uuid + EE placement)
            model_info = self._extract_3d_model_info(easyeda_data)

            if not model_info:
                self.logger.warning("No 3D model info found")
                return models

            uuid = model_info["uuid"]
            model_urls = {
                "obj": ENDPOINT_3D_MODEL_OBJ.format(uuid=uuid),
                "step": ENDPOINT_3D_MODEL_STEP.format(uuid=uuid),
            }

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

            # Convert OBJ to WRL (with centering + EE offset)
            if obj_content:
                wrl_path = output_dir / f"{lcsc_id}.wrl"
                try:
                    wrl_content = self._convert_obj_to_wrl(
                        obj_content=obj_content,
                        translation_x=model_info["translation_x"],
                        translation_y=model_info["translation_y"],
                        translation_z=model_info["translation_z"],
                    )
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

    def _extract_3d_model_info(
        self, easyeda_data: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Extract full 3D model metadata (uuid + translation + rotation) from SVGNODE.

        EasyEDA stores the 3D model reference in the footprint shape array as:
          SVGNODE~{"attrs":{"uuid":..., "c_origin":"x,y", "z":"...", "c_rotation":"x,y,z"}}

        Translation is computed as (c_origin - canvas_origin) converted mils→mm via /3.937.
        Returns None if SVGNODE or required attrs are missing.
        """
        try:
            package_detail = easyeda_data.get("packageDetail", {})
            data_str = package_detail.get("dataStr", {})
            shape_array = data_str.get("shape", [])
            head = data_str.get("head", {})

            canvas_x = float(head.get("x", 0))
            canvas_y = float(head.get("y", 0))

            for line in shape_array:
                if not isinstance(line, str):
                    continue
                parts = line.split("~", 1)
                if len(parts) < 2 or parts[0] != "SVGNODE":
                    continue
                try:
                    svg_data = json.loads(parts[1])
                except json.JSONDecodeError:
                    continue

                attrs = svg_data.get("attrs", {})
                uuid = attrs.get("uuid")
                if not uuid:
                    continue

                # c_origin: "x,y" in EasyEDA canvas units (10-mil / 0.254 mm each),
                # relative to canvas. Upstream reference: Easyeda3dModelImporter.parse_3d_model_info
                c_origin_raw = attrs.get("c_origin")
                if c_origin_raw is None:
                    # No placement info — translation stays zero (canvas_x/y cancel out)
                    co_x, co_y = canvas_x, canvas_y
                else:
                    try:
                        co_x, co_y = [float(v) for v in c_origin_raw.split(",")]
                    except (ValueError, AttributeError):
                        co_x, co_y = canvas_x, canvas_y

                # Translation in mm. Y is negated to convert EasyEDA screen-space
                # (Y-down) to KiCad board-space (Y-up). Z is in canvas units too,
                # so it's scaled by the same factor.
                translation_x = (co_x - canvas_x) / 3.937
                translation_y = -(co_y - canvas_y) / 3.937

                try:
                    translation_z = float(attrs.get("z", 0)) / 3.937
                except (ValueError, TypeError):
                    translation_z = 0.0

                rotation_raw = attrs.get("c_rotation", "0,0,0")
                try:
                    rx, ry, rz = [float(v) for v in rotation_raw.split(",")]
                except (ValueError, AttributeError):
                    rx, ry, rz = 0.0, 0.0, 0.0

                self.logger.info(
                    f"Found 3D model: uuid={uuid} "
                    f"translation=({translation_x:.3f},{translation_y:.3f},{translation_z:.3f}) "
                    f"rotation=({rx},{ry},{rz})"
                )

                return {
                    "uuid": uuid,
                    "translation_x": translation_x,
                    "translation_y": translation_y,
                    "translation_z": translation_z,
                    "rotation": (rx, ry, rz),
                    "title": attrs.get("title", ""),
                }

            return None

        except Exception as e:
            self.logger.error(f"Error extracting 3D model info: {e}", exc_info=True)
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

    def _convert_obj_to_wrl(
        self,
        obj_content: str,
        translation_x: float = 0.0,
        translation_y: float = 0.0,
        translation_z: float = 0.0,
    ) -> Optional[str]:
        """
        Convert OBJ format to WRL (VRML) with centering and EE placement offset.

        Applies:
          1. XY centering on (0,0) based on OBJ bbox center.
          2. Z shift so model bottom sits at z=0.
          3. EasyEDA placement offset (c_origin - canvas_origin) in mm.

        Ported from easyeda2kicad.py v1.0.1 export_kicad_3d_model.generate_wrl_model.
        """
        try:
            if not obj_content:
                return None

            materials = self._extract_obj_materials(obj_content)

            # Compute centering offsets from bbox
            offset_x, offset_y, offset_z = 0.0, 0.0, 0.0
            bbox = self._get_obj_bbox(obj_content)
            if bbox:
                (x_min, x_max), (y_min, y_max), (z_min, _) = bbox
                offset_x = -(x_min + x_max) / 2.0
                offset_y = -(y_min + y_max) / 2.0
                offset_z = -z_min

            # Add EE placement offset (already in mm)
            offset_x += translation_x
            offset_y += translation_y
            offset_z += translation_z

            self.logger.debug(
                f"3D centering offset: X={offset_x:.2f} Y={offset_y:.2f} Z={offset_z:.2f}"
            )

            vertices = self._extract_obj_vertices(
                obj_content,
                offset_x=offset_x,
                offset_y=offset_y,
                offset_z=offset_z,
            )

            wrl_header = """#VRML V2.0 utf8
# 3D model generated by kicad-lcsc-manager
# Based on easyeda2kicad.py v1.0.1
"""
            raw_wrl = wrl_header

            shapes = obj_content.split("usemtl")[1:]
            if not shapes:
                self.logger.warning("OBJ has no usemtl sections; no geometry exported")
                return None

            for shape in shapes:
                lines = shape.splitlines()
                if not lines:
                    continue
                material_name = lines[0].replace(" ", "")
                material = materials.get(material_name)
                if material is None:
                    self.logger.warning(f"Material not found: {material_name}, skipping")
                    continue

                index_counter = 0
                link_dict = {}
                coord_index = []
                points = []
                for line in lines[1:]:
                    if line.strip() and line.split()[0] == "f":
                        face = [int(tok.split("/")[0]) for tok in line.split()[1:]]
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

                # ambientIntensity: Rec.601 luminance from Ka
                try:
                    ka = material.get("ambient_color", ["0.2", "0.2", "0.2"])
                    ambient_intensity = round(
                        0.299 * float(ka[0]) + 0.587 * float(ka[1]) + 0.114 * float(ka[2]),
                        4,
                    )
                except (ValueError, IndexError):
                    ambient_intensity = 0.2

                transparency = material.get("transparency", "0")
                diffuse_color = " ".join(material.get("diffuse_color", ["0.8", "0.8", "0.8"]))
                specular_color = " ".join(material.get("specular_color", ["0.5", "0.5", "0.5"]))

                shape_str = textwrap.dedent(
                    f"""
        Shape{{
            appearance Appearance {{
                material  Material {{
                    diffuseColor {diffuse_color}
                    specularColor {specular_color}
                    ambientIntensity {ambient_intensity}
                    transparency {transparency}
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
                raw_wrl += shape_str

            return raw_wrl

        except Exception as e:
            self.logger.error(f"Error converting OBJ to WRL: {e}", exc_info=True)
            return None

    def _extract_obj_materials(self, obj_content: str) -> Dict[str, Dict[str, Any]]:
        """
        Extract material definitions from OBJ content.
        Ported from easyeda2kicad.py v1.0.1 export_kicad_3d_model.get_materials.
        """
        material_regex = "newmtl .*?endmtl"
        matches = re.findall(pattern=material_regex, string=obj_content, flags=re.DOTALL)

        materials = {}
        for match in matches:
            material = {}
            material_id = None
            for value in match.splitlines():
                if value.startswith("newmtl"):
                    material_id = value.split()[1]
                elif value.startswith("Ka"):
                    material["ambient_color"] = value.split()[1:]
                elif value.startswith("Kd"):
                    material["diffuse_color"] = value.split()[1:]
                elif value.startswith("Ks"):
                    material["specular_color"] = value.split()[1:]
                elif value.startswith("d "):
                    # EasyEDA d = transparency directly (matches VRML semantics).
                    # Note leading space to disambiguate from Kd/Ks/Ka lines.
                    try:
                        material["transparency"] = str(round(float(value.split()[1]), 4))
                    except (ValueError, IndexError):
                        material["transparency"] = "0"

            if material_id is not None:
                materials[material_id] = material
        return materials

    def _extract_obj_vertices(
        self,
        obj_content: str,
        offset_x: float = 0.0,
        offset_y: float = 0.0,
        offset_z: float = 0.0,
    ) -> List[str]:
        """
        Extract vertices from OBJ content, apply offsets, convert mm→inch (/2.54).
        Ported from easyeda2kicad.py v1.0.1 export_kicad_3d_model.get_vertices.
        """
        result = []
        for line in obj_content.splitlines():
            parts = line.split()
            if len(parts) < 4 or parts[0] != "v":
                continue
            try:
                x, y, z = float(parts[1]), float(parts[2]), float(parts[3])
            except ValueError:
                continue
            result.append(
                " ".join(
                    [
                        str(round((x + offset_x) / 2.54, 4)),
                        str(round((y + offset_y) / 2.54, 4)),
                        str(round((z + offset_z) / 2.54, 4)),
                    ]
                )
            )
        return result

    def _get_obj_bbox(
        self, obj_content: str
    ) -> Optional[Tuple[Tuple[float, float], Tuple[float, float], Tuple[float, float]]]:
        """
        Compute OBJ vertex bounding box.

        Returns:
            ((x_min, x_max), (y_min, y_max), (z_min, z_max)) or None if no vertices.

        Ported from easyeda2kicad.py v1.0.1 export_kicad_3d_model._get_obj_bbox.
        """
        x_vals, y_vals, z_vals = [], [], []
        for line in obj_content.splitlines():
            parts = line.split()
            if len(parts) < 4 or parts[0] != "v":
                continue
            try:
                x_vals.append(float(parts[1]))
                y_vals.append(float(parts[2]))
                z_vals.append(float(parts[3]))
            except ValueError:
                continue

        if not x_vals:
            return None

        return (
            (min(x_vals), max(x_vals)),
            (min(y_vals), max(y_vals)),
            (min(z_vals), max(z_vals)),
        )

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
