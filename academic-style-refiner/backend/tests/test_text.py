from app.chunker import segment, split_document
from app.metrics import analyze, count_syllables, mtld
from app.protect import check_fidelity, mask, unmask
from app.textutils import split_sentences

PARA = (
    "Prior work (Smith et al., 2020; Lee, 2019a) reported a 12.5% gain [3, 4]. "
    "See https://example.org/data and doi:10.1000/xyz123. "
    'As Jones put it, "the effect is robust". The model uses $x^2 + y$.'
)


def test_mask_roundtrip_and_spans():
    m = mask(PARA)
    assert set(m.spans.values()) == {
        "(Smith et al., 2020; Lee, 2019a)",
        "[3, 4]",
        "https://example.org/data",
        "doi:10.1000/xyz123",
        '"the effect is robust"',
        "$x^2 + y$",
    }
    assert unmask(m.text, m.spans) == PARA


def test_fidelity_detects_missing_and_duplicate_tokens_and_numbers():
    m = mask(PARA)
    assert check_fidelity(m, m.text) is None
    assert "missing" in check_fidelity(m, m.text.replace("⟦P1⟧", ""))
    assert "more than once" in check_fidelity(m, m.text + " ⟦P1⟧")
    assert "not in the source" in check_fidelity(m, m.text + " ⟦P99⟧")
    assert "12.5%" in check_fidelity(m, m.text.replace("12.5%", "13%"))


def test_sentence_split_respects_abbreviations():
    text = 'Smith et al. found an effect. This holds, e.g. in Fig. 2. Dr. J. Doe said "yes." Next one.'
    assert split_sentences(text) == [
        "Smith et al. found an effect.",
        "This holds, e.g. in Fig. 2.",
        'Dr. J. Doe said "yes."',
        "Next one.",
    ]


def test_split_document_kinds():
    doc = (
        "# Introduction\n\nThis is a paragraph that\nwas hard wrapped.\n\n"
        "- first item\n- second item\n\n2.1 Methods\n\nAnother paragraph here.\n\n"
        "References\n\nSmith, J. (2020). A paper. Journal."
    )
    blocks = split_document(doc)
    assert [b.kind for b in blocks] == [
        "heading",
        "paragraph",
        "list",
        "heading",
        "paragraph",
        "heading",
        "reference",
    ]
    assert blocks[1].text == "This is a paragraph that was hard wrapped."
    assert blocks[2].text == "- first item\n- second item"


def test_segment_splits_long_paragraphs_evenly():
    sentence = "The quick analysis of the data showed a clear trend in the results. "
    para = sentence * 60  # 720 words
    parts = segment(para, 320)
    assert len(parts) == 3
    assert " ".join(parts) == " ".join(para.split())
    sizes = [len(p.split()) for p in parts]
    assert max(sizes) - min(sizes) <= 24


def test_metrics_sanity():
    assert count_syllables("analysis") >= 3
    assert count_syllables("the") == 1
    m = analyze("Short one. This sentence is quite a bit longer than the first one was.\n\nThird.")
    assert m.paragraphs == 2 and m.sentences == 3
    assert m.sentence_length_variation > 0.5
    assert 0 < m.type_token_ratio <= 1
    repetitive = " ".join(["the cat sat on the mat"] * 30)
    varied = " ".join(f"word{i}" for i in range(180))
    assert mtld(repetitive.split()) < mtld(varied.split())
