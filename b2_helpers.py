import boto3
from botocore.client import Config
from flask import current_app
import logging

def upload_to_b3(file, filename):
    try:
        # Get configuration from app
        key_id = current_app.config.get('B2_KEY_ID')
        app_key = current_app.config.get('B2_APP_KEY')
        bucket_name = current_app.config.get('B2_BUCKET_NAME')
        endpoint_url = current_app.config.get('B2_ENDPOINT_URL')
        
        # Validate configuration
        if not all([key_id, app_key, bucket_name, endpoint_url]):
            current_app.logger.error("Missing Backblaze configuration")
            return None

        # Create S3 client with proper configuration
        s3 = boto3.client(
            's3',
            aws_access_key_id=key_id,
            aws_secret_access_key=app_key,
            endpoint_url=endpoint_url,
            config=Config(
                signature_version='s3v4',  # Required for Backblaze
                s3={'addressing_style': 'virtual'},  # Required for Backblaze
                region_name='us-east-005'  # Must match your endpoint
            )
        )
        
        # Reset file pointer to beginning
        file.seek(0)
        
        # Upload file
        s3.upload_fileobj(
            file,
            bucket_name,
            filename,
            ExtraArgs={
                'ACL': 'public-read',
                'ContentType': file.content_type
            }
        )
        
        # Construct public URL
        public_url = f"{endpoint_url}/{bucket_name}/{filename}"
        return public_url
        
    except Exception as e:
        current_app.logger.error(f"Boto3 upload failed: {str(e)}", exc_info=True)
        return None