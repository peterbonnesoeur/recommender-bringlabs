import os
import json
import boto3
import dotenv
from moto import mock_aws
import botocore.exceptions
from recipeExtractor import RecipeExtractor


# Allows to load environment variables from a .env file
# It is used for the OPENAI_API_KEY
dotenv.load_dotenv(dotenv.find_dotenv())


# Testing with mock AWS services using moto
@mock_aws
def test_sqs_firehose_integration():
    # Disable Signature: Disabling signature signing prevents boto3 from attempting to validate the credentials with AWS.
    config = botocore.config.Config(signature_version=botocore.UNSIGNED)

    # Create a mock S3 bucket
    s3 = boto3.resource("s3", region_name="us-east-1", config=config)
    bucket_name = "mock-bucket"
    s3.create_bucket(Bucket=bucket_name)

    # Create a mock SQS queue
    sqs = boto3.client("sqs", region_name="us-east-1", config=config)
    queue_name = "mock-queue"
    sqs_queue = sqs.create_queue(QueueName=queue_name)
    queue_url = sqs_queue["QueueUrl"]

    # Create a mock Firehose delivery stream
    firehose = boto3.client("firehose", region_name="us-east-1", config=config)
    firehose_stream_name = "mock-firehose"
    firehose.create_delivery_stream(
        DeliveryStreamName=firehose_stream_name,
        S3DestinationConfiguration={
            "RoleARN": "arn:aws:iam::123456789012:role/mock-firehose-role",
            "BucketARN": f"arn:aws:s3:::{bucket_name}",
            "Prefix": "firehose/",
        },
    )

    # Send a sample URL message to the SQS queue
    sample_url = (
        "https://www.marmiton.org/recettes/recette_cinnamon-rolls-de-karine_327467.aspx"
    )
    sqs.send_message(QueueUrl=queue_url, MessageBody=json.dumps({"url": sample_url}))

    # Receive message from SQS queue
    response = sqs.receive_message(QueueUrl=queue_url, MaxNumberOfMessages=1)

    print(f"Received messages: {response}")

    messages = response.get("Messages", [])
    if messages:
        for message in messages:
            try:
                # Extract URL from the message body
                body = json.loads(message["Body"])
                url = body.get("url")
                if not url:
                    raise ValueError("No URL found in the message body.")

                # Extract recipe information
                extractor = RecipeExtractor(api_key=os.getenv("OPENAI_API_KEY"))
                recipe_info = extractor.extract_recipe_info(url)

                print(f"Extracted recipe information: {recipe_info}")

                # Send the results to Firehose
                firehose.put_record(
                    DeliveryStreamName=firehose_stream_name,
                    Record={"Data": json.dumps(recipe_info) + "\n"},
                )
                print(f"Sent recipe information to Firehose")

                # Delete the message from the queue after successful processing
                sqs.delete_message(
                    QueueUrl=queue_url, ReceiptHandle=message["ReceiptHandle"]
                )

            except Exception as e:
                print(f"Error processing message: {e}")

    # Validate that the data was sent to the mock S3 bucket
    s3_client = boto3.client("s3", region_name="us-east-1", config=config)
    response = s3_client.list_objects_v2(Bucket=bucket_name, Prefix="firehose/")
    if "Contents" in response:
        for obj in response["Contents"]:
            print(f"Found object in mock S3: {obj['Key']}")
            # Load the object from S3
    else:
        print("No objects found in the mock S3 bucket.")

    # Validate that the data was sent to the mock S3 bucket
    # s3_client = boto3.client('s3', region_name='us-east-1', config=config)
    response = s3_client.list_objects_v2(Bucket=bucket_name, Prefix="firehose/")
    if "Contents" in response:
        for obj in response["Contents"]:
            print(f"Found object in mock S3: {obj['Key']}")
    else:
        print("No objects found in the mock S3 bucket.")


if __name__ == "__main__":
    # Test the S3 Firehose integration
    test_sqs_firehose_integration()
