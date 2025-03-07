import hashlib


class SHA256:
    def str_to_hash(self, data: str) -> str:
        hash_obj = hashlib.sha256(data.encode())
        return hash_obj.hexdigest()
