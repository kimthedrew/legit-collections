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
        if not key_id or not app_key or not bucket_name or not endpoint_url:
            current_app.logger.error("Missing Backblaze configuration")
            current_app.logger.error(f"Config: key_id={bool(key_id)}, app_key={bool(app_key)}, bucket={bucket_name}, endpoint={endpoint_url}")
            return None

        # Extract region from endpoint
        region = endpoint_url.split('.')[1]  # Extract "us-east-005" from "https://s3.us-east-005.backblazeb2.com"
        
        # Create S3 client with proper configuration
        s3 = boto3.client(
            's3',
            aws_access_key_id=key_id,
            aws_secret_access_key=app_key,
            endpoint_url=endpoint_url,
            config=Config(
                signature_version='s3v4',
                s3={'addressing_style': 'virtual'},
                region_name=region
            )
        )
        
        # Reset file pointer to beginning
        file.seek(0)
        
        # Upload file
        s3.upload_fileobj(
            Fileobj=file,
            Bucket=bucket_name,
            Key=filename,
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