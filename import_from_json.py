#!/usr/bin/env python3
"""
Import MongoDB data from JSON backup files
Usage: python import_from_json.py
"""
import json
from pathlib import Path
from pymongo import MongoClient
from tqdm import tqdm
from bson import ObjectId
from datetime import datetime

# Destination (Local)
LOCAL_URI = "mongodb://localhost:27017"
LOCAL_DB = "vaers_dev"

# Source folder - change this to where your backup is
BACKUP_DIR = Path.home() / "Desktop" / "vaers_backup"

def parse_dates(doc):
    """Recursively parse ISO datetime strings back to datetime objects"""
    if isinstance(doc, dict):
        return {k: parse_dates(v) for k, v in doc.items()}
    elif isinstance(doc, list):
        return [parse_dates(item) for item in doc]
    elif isinstance(doc, str):
        # Try to parse ISO datetime strings
        if len(doc) >= 19 and 'T' in doc:
            try:
                return datetime.fromisoformat(doc.replace('Z', '+00:00'))
            except:
                return doc
        return doc
    return doc

def import_from_json():
    """Import all collections from JSON files"""

    if not BACKUP_DIR.exists():
        print(f"❌ Backup directory not found: {BACKUP_DIR}")
        print(f"Please update BACKUP_DIR in the script to point to your backup location.")
        return

    print(f"Backup directory: {BACKUP_DIR}\n")

    print("Connecting to local MongoDB...")
    client = MongoClient(LOCAL_URI, serverSelectionTimeoutMS=5000)
    db = client[LOCAL_DB]

    # Find metadata file
    metadata_files = list(BACKUP_DIR.glob("export_metadata_*.json"))
    if metadata_files:
        with open(metadata_files[-1], 'r') as f:
            metadata = json.load(f)
        print(f"Found export from: {metadata['export_date']}\n")

    # Get all collection directories
    collection_dirs = [d for d in BACKUP_DIR.iterdir() if d.is_dir()]

    for coll_dir in collection_dirs:
        coll_name = coll_dir.name
        print(f"{'='*60}")
        print(f"Importing collection: {coll_name}")
        print(f"{'='*60}")

        collection = db[coll_name]

        # Drop existing collection
        if coll_name in db.list_collection_names():
            print(f"Dropping existing collection '{coll_name}'...")
            collection.drop()

        # Get all JSON files for this collection
        json_files = sorted(coll_dir.glob(f"{coll_name}_part*.json"))
        print(f"Found {len(json_files)} file(s)")

        total_docs = 0

        for json_file in tqdm(json_files, desc="Processing files", unit="file"):
            with open(json_file, 'r', encoding='utf-8') as f:
                docs = json.load(f)

            # Convert strings back to proper types
            for doc in docs:
                # Parse datetime strings
                doc = parse_dates(doc)

                # Convert _id strings back to ObjectId if needed
                if '_id' in doc and isinstance(doc['_id'], str):
                    try:
                        doc['_id'] = ObjectId(doc['_id'])
                    except:
                        pass  # Keep as string if not valid ObjectId

            if docs:
                collection.insert_many(docs, ordered=False)
                total_docs += len(docs)

        print(f"✓ Imported {total_docs:,} documents")

        # Import indexes
        index_file = coll_dir / "_indexes.json"
        if index_file.exists():
            print("Creating indexes...")
            with open(index_file, 'r') as f:
                indexes = json.load(f)

            for idx in indexes:
                if idx.get('name') != '_id_':  # Skip default _id index
                    try:
                        keys = list(idx['key'].items())
                        collection.create_index(keys, name=idx['name'])
                        print(f"  ✓ Created index: {idx['name']}")
                    except Exception as e:
                        print(f"  ⚠ Could not create index {idx.get('name')}: {e}")

    print(f"\n{'='*60}")
    print("✓ Import complete!")
    print(f"{'='*60}")

    # Summary
    print("\nLocal database summary:")
    for coll_name in db.list_collection_names():
        count = db[coll_name].estimated_document_count()
        print(f"  - {coll_name}: {count:,} documents")

    client.close()

if __name__ == "__main__":
    try:
        import_from_json()
    except Exception as e:
        print(f"\n❌ Error: {e}")
        raise
