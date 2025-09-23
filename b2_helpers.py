from b2sdk.v2 import B2Api, InMemoryAccountInfo, UploadSourceBytes
from b2sdk.v2.exception import B2SimpleError
from flask import current_app
import logging
import traceback

def upload_to_b2(file, filename):
    try:
        # Get configuration from app
        key_id = current_app.config.get('B2_KEY_ID')
        app_key = current_app.config.get('B2_APP_KEY')
        bucket_name = current_app.config.get('B2_BUCKET_NAME')
        
        # Log credentials (masked for security)
        key_id_debug = f"{key_id[:5]}...{key_id[-3:]}" if key_id else "Not set"
        app_key_debug = f"{app_key[:5]}...{app_key[-3:]}" if app_key else "Not set"
        current_app.logger.info(f"Using B2 Key ID: {key_id_debug}, Bucket: {bucket_name}")
        
        if not key_id or not app_key:
            current_app.logger.error("Missing B2 credentials")
            return None
        if not bucket_name:
            current_app.logger.error("Missing B2 bucket name")
            return None

        # Create an in-memory account info
        info = InMemoryAccountInfo()
        info   = InMemoryAccountInfo()
        b2_api = B2Api(info)

        try:
            b2_api.authorize_account("production", key_id, app_key)
        except B2SimpleError as us_e:
             current_app.logger.error(f"US auth failed: {us_e}")
             try:
                b2_api.authorize_account("production", key_id, app_key, realm="eu-central-001")
             except B2SimpleError as eu_e:
                current_app.logger.error(f"EU auth failed: {eu_e}")
                return None
        
        # Get the bucket
        try:
            bucket = b2_api.get_bucket_by_name(bucket_name)
        except B2SimpleError as e:
            current_app.logger.error(f"Bucket error: {str(e)}")
            return None
        
        # Read the file data
        file_data = file.read()
        
        # Upload the file
        try:
            uploaded_file = bucket.upload(
                upload_source=UploadSourceBytes(file_data),
                file_name=filename,
                content_type=file.content_type
            )
            current_app.logger.info(f"File uploaded: {uploaded_file.file_name}")
        except Exception as e:
            current_app.logger.error(f"Upload failed: {str(e)}")
            return None
        
        # Construct public URL
        public_url = b2_api.get_download_url_for_file_name(bucket_name, filename)
        return public_url
        
    except Exception as e:
        current_app.logger.error(f"Backblaze SDK error: {str(e)}")
        current_app.logger.error(traceback.format_exc())
        return None