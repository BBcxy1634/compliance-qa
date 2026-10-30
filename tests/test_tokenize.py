"""Mixed-language tokenization tests."""

from src.retrieve import tokenize


def test_mixed_language_tokenizer() -> None:
    tokens = tokenize("Amazon 电池 product compliance")
    assert "amazon" in tokens
    assert "电池" in tokens
    assert "product" in tokens
    assert "compliance" in tokens


def test_stopwords_do_not_dominate_query() -> None:
    tokens = tokenize("如何 can I sell on eBay")
    assert "ebay" in tokens
    assert "sell" in tokens
    assert "the" not in tokens
