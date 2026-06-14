from bs4 import BeautifulSoup

from app.sources.nihr import parse_nihr_opportunities
from app.sources.raeng import parse_raeng_opportunities
from app.sources.royal_society import parse_royal_society_opportunities
from app.sources.wellcome import parse_wellcome_opportunities


def soup(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "html.parser")


def test_parse_nihr_opportunities_extracts_dates_and_status() -> None:
    html = """
    <article class="card--funding">
      <p>Invention for Innovation</p>
      <a href="/funding/foo">Digital health funding call</a>
      <p>Support for NHS-facing digital health research.</p>
      <p>Opening date:</p><p>21 May 2026 at 1:00 pm</p>
      <p>Closing date:</p><p>12 August 2026 at 1:00 pm</p>
      <p>Status:</p><p>Open</p>
    </article>
    """

    opportunities = parse_nihr_opportunities("https://www.nihr.ac.uk/funding-opportunities", soup(html))

    assert len(opportunities) == 1
    assert opportunities[0].source == "NIHR"
    assert opportunities[0].title == "Digital health funding call"
    assert opportunities[0].opening_date == "21 May 2026 at 1:00 pm"
    assert opportunities[0].closing_date == "12 August 2026 at 1:00 pm"
    assert opportunities[0].status == "Open"


def test_parse_wellcome_opportunities_extracts_scheme_metadata() -> None:
    html = """
    <section>
      <a href="/research-funding/schemes/discovery-awards">Discovery Awards</a>
      <p>Funding for established researchers and teams.</p>
      <p>Discovery Research</p>
      <p>Open to applications</p>
      <p>Deadline: 30 July 2026</p>
    </section>
    """

    opportunities = parse_wellcome_opportunities("https://wellcome.org/research-funding/schemes", soup(html))

    assert len(opportunities) == 1
    assert opportunities[0].source == "Wellcome"
    assert opportunities[0].title == "Discovery Awards"
    assert opportunities[0].funding_type == "Discovery Research"
    assert opportunities[0].status == "Open"
    assert opportunities[0].closing_date == "30 July 2026"


def test_parse_royal_society_opportunities_extracts_grant_listing_dates() -> None:
    html = """
    <section>
      <a href="/grants/entrepreneur-in-residence/">
        Entrepreneur in Residence A scheme to increase knowledge of industrial science.
        Closing 19 August 2026 Open
      </a>
    </section>
    """

    opportunities = parse_royal_society_opportunities(
        "https://royalsociety.org/grants/search/grant-listings/",
        soup(html),
    )

    assert len(opportunities) == 1
    assert opportunities[0].source == "Royal Society"
    assert opportunities[0].title == "Entrepreneur in Residence"
    assert opportunities[0].closing_date == "19 August 2026"
    assert opportunities[0].status == "Open"


def test_parse_raeng_opportunities_extracts_programme_cards() -> None:
    html = """
    <section>
      <h2>Research Fellowships</h2>
      <p>NOW OPEN. Supporting early-career researchers to become future research leaders in engineering.</p>
      <p>Closing date:</p><p>17 September 2026</p>
      <a href="/programmes-and-prizes/programmes/uk-grants-and-prizes/support-for-research/research-fellowships/">Find out more</a>
    </section>
    """

    opportunities = parse_raeng_opportunities(
        "https://raeng.org.uk/programmes-and-prizes/programmes/uk-grants-and-prizes/support-for-research/",
        soup(html),
    )

    assert len(opportunities) == 1
    assert opportunities[0].source == "Royal Academy of Engineering"
    assert opportunities[0].title == "Research Fellowships"
    assert opportunities[0].status == "Open"
    assert opportunities[0].closing_date == "17 September 2026"
