from db.models.embedding import Embedding
from db.session import SessionLocal


def insert_embedding(source: str, url: str, embedding: list[float] | None) -> Embedding:
    """Insert an embedding record into the database.

    Args:
        source: The source platform (e.g. 'x').
        url: The original URL that was processed.
        embedding: The 1024-dim vector, or None if not yet generated.

    Returns:
        The created Embedding row.
    """
    with SessionLocal() as session:
        record = Embedding(source=source, url=url, embedding=embedding)
        session.add(record)
        session.commit()
        session.refresh(record)
        return record
