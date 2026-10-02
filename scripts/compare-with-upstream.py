"""
Side-by-side diff of our converters vs upstream easyeda2kicad.py for a
specific component. Runs symbol, footprint, and 3D model through both
pipelines on the same raw EasyEDA JSON.

Usage:
    python3 scripts/compare-with-upstream.py [LCSC_ID]

Default LCSC ID: C2040 (Raspberry Pi RP2040).

Touches the network (LCSC API).

Requires the *external* upstream package to be importable for symbol +
3D comparison, since we only vendor the footprint subset. Either pip
install easyeda2kicad, or point PYTHONPATH at a clone:

    PYTHONPATH=/tmp/easyeda2kicad python3 scripts/compare-with-upstream.py
"""
import argparse
import difflib
import os
import re
import sys
import tempfile
from pathlib import Path

PLUGINS_PATH = str(Path(__file__).parent.parent / "plugins")
sys.path.insert(0, PLUGINS_PATH)

# Also allow importing the external upstream package as a fallback for
# symbol + 3D pipelines (we only vendor the footprint subset).
if os.environ.get("UPSTREAM_PATH"):
    sys.path.insert(0, os.environ["UPSTREAM_PATH"])
else:
    sys.path.insert(0, "/tmp/easyeda2kicad")

from lcsc_manager.api.lcsc_api import LCSCAPIClient
from lcsc_manager.converters.footprint_converter import FootprintConverter
from lcsc_manager.converters.symbol_converter import SymbolConverter
from lcsc_manager.converters.model_3d_converter import Model3DConverter


# ─── helpers ─────────────────────────────────────────────────────────

ANSI_GREEN = "\033[32m"
ANSI_RED = "\033[31m"
ANSI_DIM = "\033[2m"
ANSI_RESET = "\033[0m"


def banner(label: str) -> None:
    bar = "─" * (len(label) + 4)
    print(f"\n{bar}\n  {label}\n{bar}")


def show_diff(label_a: str, text_a: str, label_b: str, text_b: str,
              context: int = 1, max_lines: int = 80) -> bool:
    """Print a unified diff. Return True if identical."""
    if text_a == text_b:
        print(f"  {ANSI_GREEN}✓ {label_a} == {label_b} (byte-identical){ANSI_RESET}")
        return True
    diff = list(difflib.unified_diff(
        text_a.splitlines(keepends=True),
        text_b.splitlines(keepends=True),
        fromfile=label_a,
        tofile=label_b,
        n=context,
    ))
    print(f"  {ANSI_RED}✗ {label_a} != {label_b} ({len(diff)} diff lines){ANSI_RESET}")
    truncated = diff[:max_lines]
    sys.stdout.write("".join(truncated))
    if len(diff) > max_lines:
        print(f"  {ANSI_DIM}… {len(diff) - max_lines} more diff lines truncated{ANSI_RESET}")
    return False


# ─── footprint ───────────────────────────────────────────────────────

def compare_footprint(raw, comp) -> None:
    """Use the vendored upstream we ship as the upstream reference, since
    that's what our converter delegates to and what shipped in v0.5.0."""
    from lcsc_manager.vendor.easyeda2kicad.easyeda.easyeda_importer import (
        EasyedaFootprintImporter,
    )
    from lcsc_manager.vendor.easyeda2kicad.kicad.export_kicad_footprint import (
        ExporterFootprintKicad,
    )

    fc = FootprintConverter()
    ours = fc.convert(raw, comp)

    ee = EasyedaFootprintImporter(easyeda_cp_cad_data=raw).output
    exp = ExporterFootprintKicad(footprint=ee)
    with tempfile.TemporaryDirectory() as tmp:
        out = os.path.join(tmp, f"{ee.info.name}.kicad_mod")
        exp.export(
            footprint_full_path=out,
            model_3d_path="${KIPRJMOD}/libs/lcsc/3dmodels",
            model_3d_extension="wrl",
        )
        theirs = open(out, encoding="utf-8").read()

    # Normalize the three intentional deltas we documented in v0.5.0
    def norm(t):
        t = re.sub(r"\(module\s+\S+", "(module <NAME>", t)
        t = re.sub(r"\(fp_text value\s+\S+", "(fp_text value <NAME>", t)
        t = re.sub(r'\(pad\s+"?[^"\s]*\((\d+)\)"?\s+', r"(pad \1 ", t)
        return t

    our_pads = ours.count("(pad ")
    their_pads = theirs.count("(pad ")
    print(f"  pads: ours={our_pads}  upstream={their_pads}")
    show_diff("ours (norm.)", norm(ours), "upstream (norm.)", norm(theirs))


# ─── symbol ──────────────────────────────────────────────────────────

def compare_symbol(raw, comp) -> None:
    sc = SymbolConverter()
    ours = sc.convert(raw, comp)

    try:
        from easyeda2kicad.easyeda.easyeda_importer import EasyedaSymbolImporter
        from easyeda2kicad.kicad.export_kicad_symbol import ExporterSymbolKicad
    except ImportError as e:
        print(f"  ⚠ Upstream easyeda2kicad not importable ({e}). Showing ours only.")
        print("  ours:", ours.count("(pin "), "pins,", len(ours), "chars")
        return

    try:
        ee_sym = EasyedaSymbolImporter(easyeda_cp_cad_data=raw).output
    except Exception as e:
        print(f"  ⚠ Upstream importer failed on this JSON: {type(e).__name__}: {e}")
        print(f"  ours: {ours.count('(pin ')} pins")
        return

    # version=None ⇒ upstream calls read_symbol_lib_version on a path, which fails.
    # Force a known version (6 = KiCad 6, our converter targets the same family).
    exp = ExporterSymbolKicad(symbol=ee_sym, version=6)
    theirs = exp.export(footprint_lib_name="lcsc_footprints")

    our_pins = ours.count("(pin ")
    their_pins = theirs.count("(pin ")
    print(f"  pins: ours={our_pins}  upstream={their_pins}")
    show_diff("ours", ours, "upstream", theirs, max_lines=120)


# ─── 3D model ────────────────────────────────────────────────────────

def compare_3d(raw, comp) -> None:
    """Compare our WRL and STEP byte outputs against upstream's."""
    try:
        from easyeda2kicad.easyeda.easyeda_importer import Easyeda3dModelImporter
        from easyeda2kicad.kicad.export_kicad_3d_model import Exporter3dModelKicad
    except ImportError as e:
        print(f"  ⚠ Upstream easyeda2kicad not importable ({e}). Skipping 3D.")
        return

    lcsc_id = comp.get("lcsc_id", "unknown")

    # ours
    mc = Model3DConverter()
    with tempfile.TemporaryDirectory() as tmp_ours:
        mc.process_component_model(raw, comp, Path(tmp_ours))
        our_wrl = (Path(tmp_ours) / f"{lcsc_id}.wrl")
        our_step = (Path(tmp_ours) / f"{lcsc_id}.step")
        our_wrl_text = our_wrl.read_text(encoding="utf-8") if our_wrl.exists() else None
        our_step_bytes = our_step.read_bytes() if our_step.exists() else None

    # theirs
    importer = Easyeda3dModelImporter(easyeda_cp_cad_data=raw, download_raw_3d_model=True)
    ee3d = importer.output
    if ee3d is None:
        print("  ⚠ Upstream couldn't fetch a 3D model. Skipping.")
        return
    exp = Exporter3dModelKicad(model_3d=ee3d)
    with tempfile.TemporaryDirectory() as tmp_theirs:
        ok = exp.export(output_dir=tmp_theirs)
        their_wrl = next(iter(Path(tmp_theirs).glob("*.wrl")), None)
        their_step = next(iter(Path(tmp_theirs).glob("*.step")), None)
        their_wrl_text = their_wrl.read_text(encoding="utf-8") if their_wrl else None
        their_step_bytes = their_step.read_bytes() if their_step else None

    # WRL is text — diff
    if our_wrl_text and their_wrl_text:
        print(f"  wrl: ours={len(our_wrl_text)}B  upstream={len(their_wrl_text)}B")
        show_diff("ours.wrl", our_wrl_text, "upstream.wrl", their_wrl_text,
                  max_lines=40)
    else:
        print(f"  ⚠ WRL missing — ours={bool(our_wrl_text)}  upstream={bool(their_wrl_text)}")

    # STEP is binary — just compare bytes / sizes
    if our_step_bytes is not None and their_step_bytes is not None:
        if our_step_bytes == their_step_bytes:
            print(f"  {ANSI_GREEN}✓ step bytes identical ({len(our_step_bytes)}B){ANSI_RESET}")
        else:
            print(f"  {ANSI_RED}✗ step differs: ours={len(our_step_bytes)}B  "
                  f"upstream={len(their_step_bytes)}B{ANSI_RESET}")
    else:
        print(f"  ⚠ STEP missing — ours={bool(our_step_bytes)}  upstream={bool(their_step_bytes)}")


# ─── main ────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("lcsc_id", nargs="?", default="C2040")
    args = parser.parse_args()

    client = LCSCAPIClient()
    print(f"Fetching {args.lcsc_id} from LCSC API…")
    comp = client.search_component(args.lcsc_id)
    if comp is None:
        sys.exit(f"{args.lcsc_id}: not found")
    raw = comp["easyeda_data"]
    print(f"  → {comp.get('name', '(no name)')}  package={comp.get('package', '?')}")

    banner("SYMBOL")
    compare_symbol(raw, comp)

    banner("FOOTPRINT")
    compare_footprint(raw, comp)

    banner("3D MODEL")
    compare_3d(raw, comp)


if __name__ == "__main__":
    main()
