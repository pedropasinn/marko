class PersistenceConflictError(ValueError):
    pass


class PersistenceIntegrityError(ValueError):
    pass


class UnsupportedSchemaError(ValueError):
    pass
