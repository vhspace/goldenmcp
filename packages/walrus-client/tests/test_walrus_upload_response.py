"""Walrus publisher response parsing."""

from goldenmcp_walrus.client import parse_upload_blob_id


def test_parse_upload_blob_id_from_newly_created():
    result = {
        "newlyCreated": {
            "blobObject": {
                "blobId": "xQKr2sSnhLnC4GW1_BI7WYwA_grlMUTBeMMJGyyj_-g",
                "id": "0x656bd5be4ff53d5a358532cff9c9e1a1ee66765db0bd55b66bb0d11f47fb4b76",
            }
        }
    }
    assert parse_upload_blob_id(result) == "xQKr2sSnhLnC4GW1_BI7WYwA_grlMUTBeMMJGyyj_-g"


def test_parse_upload_blob_id_from_already_certified():
    result = {
        "alreadyCertified": {
            "blobId": "M4hsZGQ1oCktdzegB6HnI6Mi28S2nqOPHxK-W7_4BUk",
        }
    }
    assert parse_upload_blob_id(result) == "M4hsZGQ1oCktdzegB6HnI6Mi28S2nqOPHxK-W7_4BUk"


def test_parse_upload_blob_id_from_flat_response():
    assert parse_upload_blob_id({"blobId": "flat-id"}) == "flat-id"
