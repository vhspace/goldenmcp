"""Walrus publisher response parsing."""

from goldenmcp_walrus.client import parse_upload_blob_id


def test_parse_upload_blob_id_from_newly_created():
    result = {
        "newlyCreated": {
            "blobObject": {
                "blobId": "xQKr2sSnhLnC4GW1_BI7WYwA_grlMUTBeMMJGyyj_-g",
            }
        }
    }
    assert parse_upload_blob_id(result) == "xQKr2sSnhLnC4GW1_BI7WYwA_grlMUTBeMMJGyyj_-g"


def test_parse_upload_blob_id_from_already_certified():
    result = {"alreadyCertified": {"blobId": "M4hsZGQ1oCktdzegB6HnI6Mi28S2nqOPHxK-W7_4BUk"}}
    assert parse_upload_blob_id(result) == "M4hsZGQ1oCktdzegB6HnI6Mi28S2nqOPHxK-W7_4BUk"
