"""The fresh-pair path must use the published notebook531-capable Source image."""
import hashlib
import json
from pathlib import Path

import pytest
import qualification_proposal as proposal
import prospective_source_qualification_workspace as source
import test_prospective531_pair as pair

HERE=Path(__file__).parent
NEW='ghcr.io/mul-cps/e2x-course-hub@sha256:dbaad51899ccb634f5a07c44bd9f7022dbca71724d7cfd66e5d67abf9d569ace'
OLD='ghcr.io/mul-cps/e2x-course-hub@sha256:51f7f392397e41be512b356fbee91980fb233296cee7557d25a758b99b045f44'


def test_prospective_tools_pin_the_actual_published_consumer():
    assert proposal.CANDIDATE_SOURCE_IMAGE==source.SOURCE_IMAGE==NEW


def test_prospective_pair_accepts_new_consumer_and_rejects_legacy_incapable_consumer():
    values,peer=pair.pair_fixture()
    for target in (values[2],peer):target['source_instance']['image']=NEW
    assert pair.render(values,peer)['acceptance.json']['hardware_qualified'] is False
    for target in (values[2],peer):target['source_instance']['image']=OLD
    with pytest.raises(ValueError):pair.render(values,peer)


def test_candidate_source_closure_is_versioned_separately_from_legacy_closure():
    path=HERE/'source531-qualification-closure.json'
    assert path.exists(), 'Published consumer module closure is required'
    data=json.loads(path.read_bytes());old=json.loads((HERE/'source51f-runtime-closure-20261015.json').read_bytes())
    assert set(data['modules'])==set(old['modules'])
    assert data['modules']['cps_compute.native_qualification']=='37815659d250e2f1ee9e77bbdb5ebcfe163bccea5206831943b469d26e584c6a'
    assert all(data['modules'][k]==v for k,v in old['modules'].items() if k.startswith('e2x_'))
    assert hashlib.sha256(path.read_bytes()).hexdigest()==proposal.CANDIDATE_SOURCE_CLOSURE_SHA256==source.SOURCE_CLOSURE_SHA256
