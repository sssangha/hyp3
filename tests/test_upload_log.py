import os
from unittest.mock import MagicMock, patch

import pytest
from botocore.stub import Stubber

import upload_log


@pytest.fixture
def cloudwatch_stubber():
    with Stubber(upload_log.CLOUDWATCH) as stubber:
        yield stubber
        stubber.assert_no_pending_responses()


@pytest.fixture
def s3_stubber():
    with Stubber(upload_log.S3) as stubber:
        yield stubber
        stubber.assert_no_pending_responses()


def test_get_log_stream():
    processing_results = {
        'Container': {
            'LogStreamName': 'mySucceededLogStream',
        },
    }
    assert upload_log.get_log_stream(processing_results) == 'mySucceededLogStream'

    processing_results = {
        'Error': 'States.TaskFailed',
        'Cause': '{"Container": {"LogStreamName": "myFailedLogStream"}}',
    }
    assert upload_log.get_log_stream(processing_results) == 'myFailedLogStream'


def test_get_log_content(cloudwatch_stubber):
    expected_params = {'logGroupName': 'myLogGroup', 'logStreamName': 'myLogStream', 'startFromHead': True}
    service_response = {
        'events': [
            {'ingestionTime': 0, 'message': 'foo', 'timestamp': 0},
            {'ingestionTime': 1, 'message': 'bar', 'timestamp': 1},
        ],
        'nextForwardToken': 'myNextToken',
    }
    cloudwatch_stubber.add_response(method='get_log_events', expected_params=expected_params,
                                    service_response=service_response)

    expected_params = {'logGroupName': 'myLogGroup', 'logStreamName': 'myLogStream', 'startFromHead': True,
                       'nextToken': 'myNextToken'}
    service_response = {'events': [], 'nextForwardToken': 'myNextToken'}
    cloudwatch_stubber.add_response(method='get_log_events', expected_params=expected_params,
                                    service_response=service_response)

    assert upload_log.get_log_content('myLogGroup', 'myLogStream') == 'foo\nbar'


def test_get_log_content_from_failed_attempts():
    cause = {
        'Status': 'FAILED',
        'StatusReason': 'Task failed to start',
        'Attempts': [
            {'Container': {'Reason': 'error message 1'}},
            {'Container': {'Reason': 'error message 2'}},
            {'Container': {'Reason': 'error message 3'}}
        ]
    }
    content = 'error message 1\nerror message 2\nerror message 3'
    assert upload_log.get_log_content_from_failed_attempts(cause) == content


def test_upload_log_to_s3(s3_stubber):
    expected_params = {
        'Body': 'myContent',
        'Bucket': 'myBucket',
        'Key': 'myJobId/myJobId.log',
        'ContentType': 'text/plain',
    }
    tag_params = {
        'Bucket': 'myBucket',
        'Key': 'myJobId/myJobId.log',
        'Tagging': {
            'TagSet': [
                {'Key': 'file_type', 'Value': 'log'}
            ]
        }
    }
    s3_stubber.add_response(method='put_object', expected_params=expected_params, service_response={})
    s3_stubber.add_response(method='put_object_tagging', expected_params=tag_params, service_response={})

    upload_log.write_log_to_s3('myBucket', 'myJobId', 'myContent')


@patch('upload_log.write_log_to_s3')
@patch('upload_log.get_log_content')
@patch.dict(os.environ, {'BUCKET': 'test-bucket'}, clear=True)
def test_lambda_handler(mock_get_log_content: MagicMock, mock_write_log_to_s3: MagicMock):
    log_content = mock_get_log_content.return_value = 'here is some test log content'
    event = {
        'prefix': 'test-prefix',
        'log_group': 'test-log-group',
        'processing_results': {'Container': {'LogStreamName': 'test-log-stream'}}
    }
    upload_log.lambda_handler(event, None)

    mock_get_log_content.assert_called_once_with('test-log-group', 'test-log-stream')
    mock_write_log_to_s3.assert_called_once_with('test-bucket', 'test-prefix', log_content)


def test_lambda_handler_no_log_stream():

    def mock_get_log_events(**kwargs):
        assert kwargs['logGroupName'] == 'test-log-group'
        assert kwargs['logStreamName'] == 'test-log-stream'
        raise upload_log.CLOUDWATCH.exceptions.ResourceNotFoundException(
            {'Error': {'Message': 'The specified log stream does not exist.'}}, 'operation_name'
        )

    event = {
        'prefix': 'test-prefix',
        'log_group': 'test-log-group',
        'processing_results': {
            'Error': '',
            'Cause': '{"Container": {"LogStreamName": "test-log-stream"},'
                     '"Status": "FAILED",'
                     '"StatusReason": "Task failed to start",'
                     '"Attempts": ['
                     '{"Container": {"Reason": "error message 1"}},'
                     '{"Container": {"Reason": "error message 2"}},'
                     '{"Container": {"Reason": "error message 3"}}]}'
        }
    }
    with patch('upload_log.CLOUDWATCH.get_log_events', mock_get_log_events), \
            patch('upload_log.write_log_to_s3') as mock_write_log_to_s3, \
            patch.dict(os.environ, {'BUCKET': 'test-bucket'}, clear=True):
        upload_log.lambda_handler(event, None)
        mock_write_log_to_s3.assert_called_once_with(
            'test-bucket', 'test-prefix', 'error message 1\nerror message 2\nerror message 3'
        )


def test_lambda_handler_resource_not_found():

    def mock_get_log_events(**kwargs):
        assert kwargs['logGroupName'] == 'test-log-group'
        assert kwargs['logStreamName'] == 'test-log-stream'
        raise upload_log.CLOUDWATCH.exceptions.ResourceNotFoundException(
            {'Error': {'Message': 'foo message'}}, 'operation_name'
        )

    event = {
        'prefix': 'test-prefix',
        'log_group': 'test-log-group',
        'processing_results': {
            'Error': '',
            'Cause': '{"Container": {"LogStreamName": "test-log-stream"},'
                     '"Status": "FAILED",'
                     '"StatusReason": "Task failed to start",'
                     '"Attempts": ['
                     '{"Container": {"Reason": "error message 1"}},'
                     '{"Container": {"Reason": "error message 2"}},'
                     '{"Container": {"Reason": "error message 3"}}]}'
        }
    }
    with patch('upload_log.CLOUDWATCH.get_log_events', mock_get_log_events):
        with pytest.raises(upload_log.CLOUDWATCH.exceptions.ResourceNotFoundException, match=r".*foo message.*"):
            upload_log.lambda_handler(event, None)
