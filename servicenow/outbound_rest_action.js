(function execute(inputs, outputs) {
    var request = new sn_ws.RESTMessageV2();
    request.setEndpoint(gs.getProperty('x_2276806_linux_0.aws_api_endpoint'));
    request.setHttpMethod('post');
    request.setRequestHeader('Content-Type', 'application/json');
    request.setRequestHeader('x-api-key', gs.getProperty('x_2276806_linux_0.aws_api_key'));

    var payload = {
        request_id: inputs.number.toString(),
        idempotency_key: inputs.number + '-' + inputs.package_name + '-' + inputs.package_version,
        servicenow_sys_id: inputs.sys_id.toString(),
        instance_id: inputs.ec2_instance_id.toString(),
        aws_region: inputs.aws_region.toString(),
        package_name: inputs.package_name.toString(),
        package_version: inputs.package_version.toString(),
        checksum_sha256: inputs.checksum_sha256.toString(),
        requested_execution_time: inputs.requested_execution_time.toString(),
        reboot_permitted: inputs.reboot_permitted === true,
        approval_status: 'approved'
    };

    request.setRequestBody(JSON.stringify(payload));
    var response = request.execute();
    outputs.status_code = response.getStatusCode();
    outputs.response_body = response.getBody();

    if (response.getStatusCode() < 200 || response.getStatusCode() >= 300) {
        throw 'AWS installation request failed: ' + response.getStatusCode() + ' ' + response.getBody();
    }
})(inputs, outputs);

