
from cloudinary_storage.storage import MediaCloudinaryStorage


"""
Ensure files uploaded to Cloudinary are stored in a private folder for security and access control
"""
private_storage = MediaCloudinaryStorage(
    resource_type="raw",
    type = "private"
)