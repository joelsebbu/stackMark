from db.models.embedding import Embedding
from db.session import SessionLocal


def insert_embedding(
    source: str,
    url: str,
    embedding: list[float] | None,
    heading: str | None = None,
    brief: str | None = None,
) -> Embedding:
    """Insert an embedding record into the database.

    Args:
        source: The source platform (e.g. 'x').
        url: The original URL that was processed.
        embedding: The 1024-dim vector, or None if not yet generated.
        heading: Short title/heading extracted from the content.
        brief: Brief summary/description of the content.

    Returns:
        The created Embedding row.
    """
    with SessionLocal() as session:
        record = Embedding(
            source=source, 
            url=url, 
            embedding=embedding,
            heading=heading, 
            brief=brief,
        )
        session.add(record)
        session.commit()
        session.refresh(record)
        return record
