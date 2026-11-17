"""The former MaterialHub inbound logistics workflow is not part of OPERA."""

def test_materialhub_inbound_workflow_routes_are_not_exposed(client):
    for path in ("/material_requisitions/", "/purchase_order/", "/delivery/", "/warehouse/", "/quality_control/", "/supplier/"):
        assert client.get(path).status_code == 404, path
