"""Cross-check ohnet.validate.SPEC against the binding's thing-types.xml.

Set OHNET_THING_TYPES to a local copy of
openhab-addons/bundles/org.openhab.binding.network/src/main/resources/OH-INF/thing/thing-types.xml
(skipped otherwise; CI fetches it).
"""

import os
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from ohnet.validate import SPEC

PATH = os.environ.get("OHNET_THING_TYPES")
pytestmark = pytest.mark.skipif(not PATH or not Path(PATH).exists(), reason="OHNET_THING_TYPES nicht gesetzt")


def _local(tag):
    return tag.rsplit("}", 1)[-1]


def test_spec_matches_binding():
    root = ET.parse(PATH).getroot()
    item_types = {ct.get("id"): next(e.text for e in ct if _local(e.tag) == "item-type")
                  for ct in root if _local(ct.tag) == "channel-type"}
    for tt in (e for e in root if _local(e.tag) == "thing-type"):
        tid = tt.get("id")
        assert tid in SPEC, f"Thing-Typ {tid} fehlt in SPEC"
        channels = {c.get("id"): item_types[c.get("typeId")] for c in tt.iter() if _local(c.tag) == "channel"}
        params = {p.get("name"): p.get("required") == "true" for p in tt.iter() if _local(p.tag) == "parameter"}
        assert SPEC[tid]["channels"] == channels, tid
        assert SPEC[tid]["params"] == set(params), tid
        # 'required' in SPEC = in XML required, ohne Default-Booleans (useIOSWakeUp etc. haben Defaults)
        assert SPEC[tid]["required"] <= {k for k, v in params.items() if v}, tid
