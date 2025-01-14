from generate_embeddings import process_batch
from core.models import Content
import pytest
from uuid import uuid4

@pytest.fixture
def mock_content_data():
    return [
        Content(
            id=uuid4(),
            title="Test Title",
            text_content="This is the first section of the mock article. It contains some introductory sentences. Here is another sentence in the first section. \n\nThis is the second section of the mock article. It contains more detailed information. Another sentence follows in the second section."
        ),
        Content(
            id=uuid4(),
            title="Test Title 2",
            text_content="This is the first section of the mock article. It contains some introductory sentences. Here is another sentence in the first section. \n\nThis is the second section of the mock article. It contains more detailed information. Another sentence follows in the second section."
        )
    ]

def test_full_process(mock_content_data):
    texts = [content.text_content for content in mock_content_data]
    embeddings = process_batch(texts)

    # Check if the processed content is not None
    assert embeddings is not None, "Processed content should not be None"
    
    # Check if the embeddings are generated
    assert len(embeddings) > 0, "Embeddings should be present in processed content"

    # Check if each embedding has at least one chunk
    for embedding in embeddings:
        assert len(embedding) > 0, "Each embedding should have at least one chunk"