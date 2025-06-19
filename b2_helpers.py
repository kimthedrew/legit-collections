from b2sdk.v2 import B2Api, InMemoryAccountInfo, UploadSourceBytes
from flask import current_app
import logging

def upload_to_b2(file, filename):
    try:
        # Get configuration from app
        key_id = current_app.config.get('B2_KEY_ID')
        app_key = current_app.config.get('B2_APP_KEY')
        bucket_name = current_app.config.get('B2_BUCKET_NAME')
        
        if not key_id or not app_key or not bucket_name:
            current_app.logger.error("Missing Backblaze configuration")
            return None

        # Create an in-memory account info
        info = InMemoryAccountInfo()
        b2_api = B2Api(info)
        
        # Authorize the account
        b2_api.authorize_account("production", key_id, app_key)
        
        # Get the bucket
        bucket = b2_api.get_bucket_by_name(bucket_name)
        
        # Read the file data
        file_data = file.read()
        
        # Upload the file
        uploaded_file = bucket.upload(
            upload_source=UploadSourceBytes(file_data),
            file_name=filename,
            content_type=file.content_type
        )
        
        # Construct public URL
        public_url = b2_api.get_download_url_for_file_name(bucket_name, filename)
        return public_url
        
    except Exception as e:
        current_app.logger.error(f"Backblaze SDK upload failed: {str(e)}", exc_info=True)
        return None