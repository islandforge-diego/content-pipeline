"""Tests for the Facebook CSV export parser (synthetic CSVs, no network/files)."""
import fb_export


def _write_exports(tmp_path):
    prof = tmp_path / "Apr-30-2026_Jun-29-2026_Profile_Activity_Daily breakdown_1.csv"
    prof.write_text(
        "Date,Impressions,Interactions,Net follows,Reactions,Comments and replies,Shares,Viewers,Views\n"
        "04/30/2026,100,10,1,8,1,1,5,200\n"
        "05/01/2026,50,5,2,4,1,0,3,100\n", encoding="utf-8")
    cont = tmp_path / "Apr-30-2026_Jun-29-2026_Content_Publish time_Summary_2.csv"
    cont.write_text(
        "Page name,Title,Post type,Views,Interactions,Permalink\n"
        "Deba Douglas,Hello world post here,Photo,300,30,x\n"
        "Deba Douglas,A great reel about flipping,Reel,700,40,y\n"
        "Other Person,not hers,Photo,9999,1,z\n", encoding="utf-8")
    return tmp_path


def test_build_facebook_personal(tmp_path):
    folder = str(_write_exports(tmp_path))
    out = fb_export.build_facebook_personal(folder, page_name="Deba Douglas", followers=5000)
    # totals come from the profile-daily export (summed)
    assert out["reach"] == 300          # Views 200 + 100
    assert out["impressions"] == 150
    assert out["engagement"] == 15
    assert out["net_follows"] == 3
    assert out["followers"] == 5000
    # views-by-type + top posts come from the content export (page-name filtered)
    d = dict(out["views_by_type"])
    assert d["Reel"] == 70.0 and d["Photo"] == 30.0
    top = out["top_posts"][0]              # the reel is top by views
    assert top["views"] == 700
    assert top["reactions"] == 0 and "permalink" in top and "type" in top
    assert "Other Person" not in str(out)  # other pages excluded
    assert out["window"].startswith("Apr 30")
