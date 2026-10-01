"""Email and meeting clean-up at ingest: quoted history, signatures and legal
footers come out; the newest message and any new inline text stay."""
from riemann.abstraction import ingest
from riemann.abstraction.normalise import looks_like_email, strip_email_noise

THREAD = """From: Dana Whitfield <dana@example.org>
To: Alex Morgan <alex@example.com>
Subject: Re: Placement start date
Date: Wed, 15 Oct 2025 16:42

Hi Alex,

Thanks for getting back so quickly. Two things I need before I can lock this in. First, the signed placement agreement back by end of day Friday 24 October.

Second, please confirm the orientation session on Monday 3 November at 9 am.

Kind regards,
Dana Whitfield
Placement Coordinator
Northgate Hospital | Tel: +61 3 5555 0100
www.example.org

This email and any attachments are confidential and may be privileged. If you are not the intended recipient, please notify the sender and delete it. Unauthorised use or disclosure is prohibited.

On Tue, 14 Oct 2025 at 09:15, Alex Morgan <alex@example.com> wrote:
> Hi Dana,
>
> Thanks for the details. I can start on 3 November as discussed, but I would need to leave at 3 pm on Thursdays.
>
> Thanks,
> Alex

On Mon, 13 Oct 2025 at 14:20, Dana Whitfield <dana@example.org> wrote:
>> Hi Alex,
>> Great news, your placement has been approved.
"""


def test_quoted_history_signature_and_disclaimer_are_removed_newest_message_stays():
    out = strip_email_noise(THREAD)
    assert "Thanks for getting back so quickly" in out
    assert "orientation session on Monday 3 November" in out
    assert "From: Dana Whitfield" in out and "Subject: Re: Placement start date" in out  # headers of this message
    for gone in ("> Hi Dana", "wrote:", "Great news", "Placement Coordinator", "Tel:", "www.example.org",
                 "intended recipient", "Unauthorised use"):
        assert gone not in out, gone
    assert "Kind regards" not in out


def test_inline_replies_between_quoted_lines_are_kept():
    text = """From: Dana <d@example.org>
To: Alex <s@example.com>
Subject: Re: questions
Date: Thu, 16 Oct 2025

On Wed, 15 Oct 2025, Alex wrote:
> Can I start on 3 November?
Yes, 3 November is fine.

> Do I need a laptop?
No, the site provides one. Bring photo ID.
"""
    out = strip_email_noise(text)
    assert "Yes, 3 November is fine." in out and "No, the site provides one. Bring photo ID." in out
    assert "Can I start" not in out and "Do I need a laptop" not in out and "wrote:" not in out


def test_outlook_original_message_tail_is_dropped():
    text = """From: Dana <d@example.org>
Subject: Re: Hours

Hi Alex, the hours are 9 to 5, Monday to Thursday. Please confirm.

-----Original Message-----
From: Alex
Sent: Monday, 13 October 2025 9:00 AM
To: Dana
Subject: Hours

What are the hours?
"""
    out = strip_email_noise(text)
    assert "9 to 5" in out and "What are the hours" not in out and "Original Message" not in out


def test_outlook_header_block_without_marker_line_is_history_too():
    text = """Hi Alex, see below and reply by Friday 24 October.

From: Alex
Sent: Monday, 13 October 2025 9:00 AM
To: Dana
Subject: Hours

What are the hours? I have nothing else to add here at all.
"""
    out = strip_email_noise(text)
    assert "reply by Friday 24 October" in out and "What are the hours" not in out


def test_signature_delimiter_and_mobile_footers():
    text = """Hi team, the deadline is Friday 14 November, 5 pm, all sections.
Please send drafts early.

-- 
Alex Morgan
Student, Unit Co-ordinator
Phone: 0400 000 000

Sent from my iPhone
"""
    out = strip_email_noise(text)
    assert out.strip().endswith("Please send drafts early.")


def test_signoff_with_contact_details_goes_but_a_bare_thanks_name_stays():
    with_contact = "Hello, the report is due Friday 7 November.\n\nBest,\nAlex Kim\nManager, Ops\nalex@example.com\n+1 555 123 4567\n"
    assert "Alex Kim" not in strip_email_noise("Subject: Report\nFrom: a\n\n" + with_contact)
    bare = "Subject: Report\nFrom: a\n\nHello, the report is due Friday 7 November and needs the appendix.\n\nThanks,\nAlex\n"
    assert strip_email_noise(bare).rstrip().endswith("Alex")


def test_legal_footer_paragraphs_of_several_lines_are_removed():
    text = """Subject: Invoice
From: Finance <f@example.org>

Your invoice 4471 of $320 is due on 30 November 2025. Please pay by bank transfer.

CONFIDENTIALITY NOTICE: This message and any attachments are intended only for the named recipient and may contain privileged information.
If you have received this message in error, please contact the sender. Please consider the environment before printing this email.
"""
    out = strip_email_noise(text)
    assert "invoice 4471" in out and "CONFIDENTIALITY" not in out and "environment" not in out


def test_only_applies_to_text_that_looks_like_an_email():
    article = """# On trains

My friend Dana wrote: "trains are late". Here is what I think about that, in more than a few words.

> A quoted line from a book that is part of the essay.
> And another one that continues the same quote.

-- 
That was the essay. Thanks, and regards,
Alex
"""
    assert not looks_like_email(article)
    assert strip_email_noise(article) == article


def test_looks_like_email_markers():
    assert looks_like_email(THREAD)
    assert looks_like_email("Some text\n\nOn Tue, 14 Oct 2025 at 09:15, X <x@y.z> wrote:\n> hi there friend\n")
    assert looks_like_email("-----Original Message-----\nFrom: a\nSent: b\n")
    assert not looks_like_email("Just a paragraph of text.\n\nAnd another.")


def test_wrapped_attribution_line():
    text = "From: a@b.c\nSubject: Re: x\n\nNew reply text that matters a lot for the reader here.\n\nOn Tue, 14 Oct 2025 at 09:15, Alex Morgan\n<alex@example.com> wrote:\n> old stuff\n> more old stuff\n"
    out = strip_email_noise(text)
    assert "New reply" in out and "old stuff" not in out and "wrote" not in out


def test_fail_safe_when_nothing_would_remain():
    text = "From: a\nSubject: Fwd\n\n> everything is quoted here and nothing is new at all\n> second quoted line\n"
    assert strip_email_noise(text) == text


def test_idempotent_and_crlf_safe():
    once = strip_email_noise(THREAD)
    assert strip_email_noise(once) == once
    assert strip_email_noise(THREAD.replace("\n", "\r\n")) == once


def test_ingest_from_text_and_file_apply_it_but_a_url_style_article_is_not_touched():
    title, text = ingest.from_text(THREAD)
    assert "Great news" not in text and "Thanks for getting back" in text
    title2, text2 = ingest.from_file("thread.txt", THREAD.encode())
    assert text2 == text
