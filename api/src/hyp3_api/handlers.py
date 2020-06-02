import json
from os import environ

from flask_cors import CORS

from hyp3_api import STEP_FUNCTION_CLIENT, connexion_app


def submit_job(body):
    parameters = body['parameters']
    job = STEP_FUNCTION_CLIENT.start_execution(
        stateMachineArn=environ['STEP_FUNCTION_ARN'],
        input=json.dumps(body),
    )
    print(job)
    response = {
        'jobId': job['executionArn'],
        'parameters': parameters,
    }
    return response


connexion_app.add_api('openapi-spec.yml')
CORS(connexion_app.app, origins=r'https?://([-\w]+\.)*asf\.alaska\.edu', supports_credentials=True)
