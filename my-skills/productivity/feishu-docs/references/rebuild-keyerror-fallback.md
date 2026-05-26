# Feishu Doc Rebuild Fallback: KeyError on batch_delete

When using `rebuild_doc_from_md.py` to completely rewrite a Feishu document, the script attempts to clear existing blocks via the `batch_delete` API.

**The Pitfall**:
If the document contains highly complex nested structures, massive tables, or specific unsupported block types, the deletion step can fail with a `KeyError: '<block_id>'` during the internal tree building/mapping phase of the script.

**Safety Mechanism**:
The script runs under an `atomic_update` wrapper. When the `KeyError` occurs, the atomic rollback will trigger and successfully restore the document to its original state using the memory snapshot, leaving it unharmed.

**The Fallback Solution**:
Since the existing document's structure cannot be parsed/deleted cleanly by the script, abandon the in-place rebuild. Instead:

1. Run `create_new_doc_from_md.py` to spawn a completely fresh document from the parsed markdown.
2. Inform the user of the new document URL and suggest deprecating or manually replacing the old one.
