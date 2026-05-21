from app.text_cleanup import clean_external_text, split_title_source


def test_clean_external_text_decodes_entities_and_removes_html():
    assert clean_external_text("Geração Z&nbsp;&nbsp;<b>corrida</b>") == "Geração Z corrida"


def test_split_title_source_removes_google_news_publisher_suffix():
    title, source = split_title_source(
        "Pesquisa: Mercado de corrida de rua tem maioria feminina - Máquina do Esporte"
    )

    assert title == "Pesquisa: Mercado de corrida de rua tem maioria feminina"
    assert source == "Máquina do Esporte"
