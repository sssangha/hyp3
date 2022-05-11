import json


def get_time_from_attempts(attempts):
    if len(attempts) == 0:
        raise ValueError('list of attempts is empty')
    attempts.sort(key=lambda attempt: attempt['StoppedAt'])
    final_attempt = attempts[-1]
    return (final_attempt['StoppedAt'] - final_attempt['StartedAt']) / 1000


def lambda_handler(event, context):
    results = event['processing_results']
    if 'Attempts' in results:
        attempts = results['Attempts']
    else:
        attempts = json.loads(results['Cause'])['Attempts']
    return get_time_from_attempts(attempts)
