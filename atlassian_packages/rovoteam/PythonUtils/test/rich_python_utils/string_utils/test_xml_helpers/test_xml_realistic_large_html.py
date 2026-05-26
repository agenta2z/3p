"""
Realistic large-scale test for xml_to_dict with complex HTML code blocks.

This test uses a real-world example of XML containing extensive HTML content
with tables, lists, and special characters that would break standard XML parsing.
"""

import pytest
from python_utils.string_utils.xml_helpers import xml_to_dict


class TestRealisticLargeHTMLCodeBlock:
    """Test real-world XML with large HTML code blocks."""

    @pytest.fixture
    def large_seo_summary_xml(self):
        """
        Real-world XML from an SEO link building channel summary.
        Contains extensive HTML with tables, lists, special characters.
        """
        return '''<StructuredResponse>
 <InstantResponse>
```html
<h1>SEO Link Building News & Updates Channel Summary</h1>
<h2>November 13-21, 2025</h2>

<h3>📊 Overview</h3>
<p>The channel had active discussions about guest posting opportunities, link exchanges, and site availability across multiple niches including SaaS, legal, property, health, and technology sectors.</p>

<hr>

<h3>🔗 Guest Post & Link Insertion Sites with Pricing</h3>

<h4>Sites Posted by Mubshar SEO (Multiple dates)</h4>
<table border="1" cellpadding="5">
<tr><th>Website</th><th>Price</th></tr>
<tr><td>cutedp.org</td><td>$80</td></tr>
<tr><td>jbsagolf.com</td><td>$75</td></tr>
<tr><td>thevtrahe.com</td><td>$85</td></tr>
<tr><td>projectmanagers.net</td><td>$95-$100</td></tr>
<tr><td>redstaglabs.com</td><td>$200</td></tr>
<tr><td>learnlaughspeak.com</td><td>$120</td></tr>
<tr><td>designnominees.com</td><td>$80</td></tr>
<tr><td>forcreators.com</td><td>$80</td></tr>
<tr><td>ordnur.com</td><td>$100</td></tr>
<tr><td>deliveredsocial.com</td><td>$210</td></tr>
<tr><td>dutable.com</td><td>$50-$60</td></tr>
<tr><td>siit.co</td><td>$75</td></tr>
<tr><td>thatericalper.com</td><td>$100-$120</td></tr>
<tr><td>entrepreneursbreak.com</td><td>$75</td></tr>
<tr><td>rankvise.com</td><td>$120</td></tr>
<tr><td>leadgenapp.io</td><td>$140</td></tr>
<tr><td>sosugary.com</td><td>$150</td></tr>
<tr><td>troopmessenger.com</td><td>$230</td></tr>
<tr><td>computertechreviews.com</td><td>$85</td></tr>
<tr><td>iemlabs.com</td><td>$85</td></tr>
<tr><td>stageandcinema.com</td><td>$80</td></tr>
<tr><td>extendsclass.com</td><td>$100</td></tr>
<tr><td>portotheme.com</td><td>$70</td></tr>
<tr><td>tamaracamerablog.com</td><td>$85</td></tr>
<tr><td>devdiggers.com</td><td>$150</td></tr>
<tr><td>atamgo.com</td><td>$75-$90</td></tr>
<tr><td>technologycounter.com</td><td>$110-$120</td></tr>
<tr><td>hrfuture.net</td><td>$99</td></tr>
<tr><td>marketinghack4u.com</td><td>$150</td></tr>
<tr><td>technogone.com</td><td>$90</td></tr>
<tr><td>fueler.io</td><td>$140</td></tr>
<tr><td>wallstreetmojo.com</td><td>$175</td></tr>
<tr><td>tieup.io</td><td>$150</td></tr>
<tr><td>webweq.com</td><td>$80-$85</td></tr>
<tr><td>voymedia.com</td><td>$120</td></tr>
<tr><td>quarule.com</td><td>$200</td></tr>
<tr><td>mylegalopinion.com</td><td>$150</td></tr>
<tr><td>datarecovee.com</td><td>$100</td></tr>
<tr><td>cnvrtool.com</td><td>$75</td></tr>
<tr><td>toolify.ai</td><td>Price available</td></tr>
<tr><td>kreafolk.com</td><td>$100</td></tr>
<tr><td>vizologi.com</td><td>$100</td></tr>
<tr><td>ecombalance.com</td><td>$200-$250</td></tr>
<tr><td>techyflavors.com</td><td>$150</td></tr>
<tr><td>techimply.com</td><td>$300</td></tr>
<tr><td>thewheon.com</td><td>$80</td></tr>
<tr><td>waseembashir.com</td><td>Available</td></tr>
<tr><td>landofcoder.com</td><td>$105</td></tr>
<tr><td>appkod.com</td><td>Available</td></tr>
<tr><td>homebriefings.com</td><td>$129</td></tr>
<tr><td>speedwaymedia.com</td><td>$72</td></tr>
<tr><td>psychreg.org</td><td>$65</td></tr>
</table>

<h4>Additional Sites Posted by Mubshar SEO (Nov 18-19)</h4>
<ul>
<li>englishsumup.com</li>
<li>coventchallenge.com</li>
<li>tamaracamera.com</li>
<li>fast4entry.com</li>
<li>thotslifey.com</li>
<li>webzeto.com</li>
<li>swsol.net.com</li>
<li>nldburma.org</li>
<li>meyvnn.com</li>
<li>fangwallet.com</li>
<li>dreamden.ai</li>
<li>mashablepartners.com</li>
<li>englishleaflet.com</li>
<li>vibromedia.com</li>
<li>nobullswipe.com</li>
<li>digitalnewsalerts.com</li>
<li>kua.ai</li>
<li>aitude.com</li>
<li>oscprofessionals.com</li>
<li>yonkerstimes.com</li>
<li>feast-magazine.co.uk</li>
<li>upbeatgeek.com</li>
<li>artoffootballblog.com</li>
<li>autisticbaker.com</li>
<li>corexta.com</li>
<li>instacare.com.pk</li>
<li>razagems.com</li>
<li>gopius.com</li>
<li>textify.ai</li>
<li>geekzilla.io</li>
<li>dmltraining.com</li>
<li>wafflebytes.com</li>
<li>logodesignteam.com</li>
<li>newswatchtv.com</li>
<li>lighttheminds.com</li>
<li>gygaldy.com</li>
<li>halt.org</li>
<li>mailsuite.com</li>
</ul>

<hr>

<h3>💰 Paid Link Exchange Sites</h3>

<h4>Posted by ayesha mounas (Nov 14)</h4>
<p><strong>UK-focused sites available for Paid GP & LI:</strong></p>
<ul>
<li>friendlyturtle.com - Zero Waste Shop UK</li>
<li>golfnews.co.uk - Golf News Magazine</li>
<li>estateagenttoday.co.uk - Estate Agency Market News</li>
<li>lettingagenttoday.co.uk - Letting Agent Tips</li>
<li>landlordtoday.co.uk - Landlord News</li>
<li>lyliarose.com</li>
<li>introducertoday.co.uk</li>
<li>bigwritehook.co.uk</li>
<li>newsdipper.co.uk</li>
<li>mt-trees.co.uk</li>
<li>guestcollab.co.uk</li>
<li>costaprices.co.uk</li>
</ul>

<h4>Posted by ali seo (Nov 18) - All sites at $60</h4>
<ul>
<li>enrichest.com</li>
<li>webweq.com</li>
<li>cnvrtool.com</li>
<li>hyscaler.com</li>
<li>kyleads.com</li>
<li>twilert.com</li>
<li>othership.com</li>
<li>digitalenterprise.org</li>
<li>ctemplar.com</li>
</ul>
<p><strong>Contact:</strong> aliseo6170@gmail.com</p>

<h4>Posted by ayesha mounas (Nov 18)</h4>
<p><strong>Available:</strong> influencersgonewildco.uk</p>

<hr>

<h3>🔄 Free Link Exchange Requests</h3>

<h4>Kaia Lennard (Nov 14)</h4>
<p>Looking for .au (Australia) websites for free link exchanges and collaboration</p>

<h4>Priyanka Koyani (Nov 16)</h4>
<p>Looking for quality free link exchanges</p>
<p><strong>Contact:</strong> priyanka.koyani@outreachdesk.com</p>

<h4>Neha (Nov 19)</h4>
<p>Needs link exchange sites - DM requested</p>

<h4>Vignesh (Nov 19)</h4>
<p><strong>Website:</strong> telecmi.com</p>
<ul>
<li>DR: 37</li>
<li>Organic Traffic: 21K+</li>
<li>TAT: Within a day</li>
<li>Looking for: Free listicle placements & link exchanges for SaaS sites in telecommunication or related sectors</li>
</ul>

<h4>Kaia Lennard (Nov 21)</h4>
<p>Looking for:</p>
<ul>
<li>Legal niche sites</li>
<li>Australia-based sites</li>
<li>Both paid or free options welcome</li>
</ul>

<hr>

<h3>📋 Site Availability Lists</h3>

<h4>Posted by Usman Ghani (Nov 13)</h4>
<ul>
<li>coda.io</li>
<li>magic.ly</li>
<li>wongcw.com</li>
<li>leadgrowdevelop.com</li>
<li>aitechdecoded.com</li>
</ul>

<h4>Posted by link builder (Nov 14)</h4>
<table border="1" cellpadding="5">
<tr><th>Website</th><th>DR</th><th>Traffic</th></tr>
<tr><td>taggbox.com</td><td>78</td><td>50K</td></tr>
<tr><td>tagshop.ai</td><td>70</td><td>15K</td></tr>
<tr><td>socialwalls.com</td><td>61</td><td>5K</td></tr>
<tr><td>tagembed.com</td><td>81</td><td>28K</td></tr>
<tr><td>insighto.ai</td><td>54</td><td>22.7K</td></tr>
<tr><td>invitereferrals.com</td><td>69</td><td>5.3K</td></tr>
<tr><td>notifyvisitors.com</td><td>75</td><td>4.1K</td></tr>
<tr><td>algoscale.com</td><td>47</td><td>12.6K</td></tr>
<tr><td>fullestop.com (Guest Post also)</td><td>57</td><td>2.8K</td></tr>
<tr><td>semidotinfotech.com (Guest Post Also)</td><td>42</td><td>-</td></tr>
<tr><td>oxygenites.com</td><td>62</td><td>1.5K</td></tr>
</table>

<h4>Posted by link builder (Nov 14) - Additional Sites</h4>
<ul>
<li>Saleshandy.com - Blog to blog</li>
<li>Codeless.io - All pages allowed</li>
</ul>

<h4>Posted by ayesha mounas (Nov 18) - Site Requests with Best Price</h4>
<p><strong>Needs these sites for link insertion (LinkedIn & Facebook profiles required):</strong></p>
<ul>
<li>embedsocial.com</li>
<li>goodfirms.co</li>
<li>thesocialshepherd.com</li>
<li>billo.app</li>
<li>netinfluencer.com</li>
<li>nogood.io</li>
<li>theleap.co</li>
<li>cohley.com</li>
<li>oxygenites.com</li>
<li>insense.pro</li>
<li>mbadmb.com</li>
<li>passionfru.it</li>
<li>buywith.com</li>
<li>viesearch.com</li>
<li>craftsmanplus.com</li>
<li>buzzbii.com</li>
<li>mrsdesireerose.com</li>
<li>jake-jorgovan.com</li>
<li>influencermarketinghub.com</li>
<li>youdji.com</li>
<li>awisee.com</li>
<li>collabstr.com</li>
<li>sociallypowerful.com</li>
<li>jiveprdigital.com</li>
<li>goviralglobal.com</li>
<li>freshcontentsociety.com</li>
<li>buffer.com</li>
<li>birdeye.com</li>
</ul>

<h4>Posted by pratik jadav (Nov 19)</h4>
<p><strong>Needs:</strong> techradar.com - DM requested</p>

<h4>Posted by ayesha mounas (Nov 19)</h4>
<p><strong>Available:</strong> breakingmuscle.com - 3 articles on hand</p>

<hr>

<h3>🎯 SaaS Sites Available (Posted by Mubshar SEO - Nov 19)</h3>
<ol>
<li>leadgenapp.io</li>
<li>troopmessenger.com</li>
<li>extendsclass.com</li>
<li>tieup.io</li>
<li>vizologi.com</li>
<li>fueler.io</li>
<li>toolify.ai</li>
<li>appkod.com</li>
<li>cnvrtool.com</li>
<li>mailsuite.com</li>
<li>landofcoder.com</li>
</ol>
<p><strong>Note:</strong> Available for guest post and link insertion</p>

<hr>

<h3>👥 New Members Joined</h3>
<ul>
<li>Syed Fawad Ali - Nov 14, 2:39 AM</li>
<li>Baqir Hussian - Nov 14, 9:08 PM</li>
<li>Tony Chen - Nov 19, 6:22 PM</li>
<li>ُEman Mohamed - Nov 20, 6:23 AM</li>
<li>George Alanis SEO - Nov 20, 10:42 PM</li>
</ul>

<hr>

<h3>💼 Professional Offers</h3>

<h4>Baqir Hussian (Nov 19)</h4>
<p>Offering paid site services:</p>
<ul>
<li>Share your budget</li>
<li>Will provide sites within budget or reasonable final price</li>
<li>Promises professional and enjoyable work experience</li>
</ul>

<hr>

<h3>📊 Key Channel Statistics</h3>
<ul>
<li><strong>Total Members:</strong> 125</li>
<li><strong>Active Contributors:</strong> Mubshar SEO, ayesha mounas, link builder, Usman Ghani, Kaia Lennard, Priyanka Koyani, Vignesh, Baqir Hussian, ali seo, Neha, pratik jadav, Tony Chen</li>
<li><strong>Date Range:</strong> November 13-21, 2025</li>
<li><strong>Primary Focus:</strong> Guest posting, link insertions, link exchanges (both paid and free)</li>
<li><strong>Price Range:</strong> $50-$300 for guest posts/link insertions</li>
</ul>

<hr>

<h3>🔑 Key Takeaways</h3>
<ol>
<li><strong>Most Active Contributor:</strong> Mubshar SEO posted the most comprehensive lists of available sites with pricing</li>
<li><strong>Popular Price Points:</strong> $75-$120 range for most sites</li>
<li><strong>Premium Sites:</strong> troopmessenger.com ($230), techimply.com ($300), deliveredsocial.com ($210)</li>
<li><strong>Budget Options:</strong> dutable.com ($50-$60), psychreg.org ($65), portotheme.com ($70)</li>
<li><strong>Niche Focus:</strong> Strong presence of SaaS, technology, marketing, and property-related sites</li>
<li><strong>Geographic Interest:</strong> Multiple requests for Australia-based (.au) sites and UK sites</li>
<li><strong>Fast TAT:</strong> Several contributors emphasized quick turnaround times (within a day)</li>
</ol>
```
 </InstantResponse>
 <TaskStatus>Completed</TaskStatus>
</StructuredResponse>'''

    def test_parse_with_protection_preserves_full_html(self, large_seo_summary_xml):
        """Test that code block protection preserves the entire HTML block."""
        result = xml_to_dict(large_seo_summary_xml)

        # Verify structure
        assert 'StructuredResponse' in result
        assert 'InstantResponse' in result['StructuredResponse']
        assert 'TaskStatus' in result['StructuredResponse']

        # The HTML should be preserved with markdown syntax
        html_content = result['StructuredResponse']['InstantResponse']
        assert '```html' in html_content
        assert '<h1>SEO Link Building News & Updates Channel Summary</h1>' in html_content

        # Verify critical XML-breaking characters are preserved
        assert '<table' in html_content
        assert '<tr>' in html_content
        assert '<td>' in html_content
        assert '&' in html_content  # Would break XML without protection

    def test_parse_extract_html_only(self, large_seo_summary_xml):
        """Test extracting just the HTML content without markdown markers."""
        result = xml_to_dict(large_seo_summary_xml, code_block_restore_group=-1)

        html_content = result['StructuredResponse']['InstantResponse']

        # Should NOT have markdown markers
        assert '```html' not in html_content or html_content.startswith('<h1>')

        # Should have HTML content
        assert '<h1>SEO Link Building News & Updates Channel Summary</h1>' in html_content
        assert '<h2>November 13-21, 2025</h2>' in html_content

    def test_verify_table_content_preserved(self, large_seo_summary_xml):
        """Test that complex table structures are preserved."""
        result = xml_to_dict(large_seo_summary_xml, code_block_restore_group=-1)
        html_content = result['StructuredResponse']['InstantResponse']

        # Check table structure
        assert '<table border="1" cellpadding="5">' in html_content
        assert '<tr><th>Website</th><th>Price</th></tr>' in html_content

        # Check specific table data
        assert '<tr><td>cutedp.org</td><td>$80</td></tr>' in html_content
        assert '<tr><td>redstaglabs.com</td><td>$200</td></tr>' in html_content
        assert '<tr><td>techimply.com</td><td>$300</td></tr>' in html_content

    def test_verify_list_content_preserved(self, large_seo_summary_xml):
        """Test that unordered and ordered lists are preserved."""
        result = xml_to_dict(large_seo_summary_xml, code_block_restore_group=-1)
        html_content = result['StructuredResponse']['InstantResponse']

        # Check unordered lists
        assert '<ul>' in html_content
        assert '<li>englishsumup.com</li>' in html_content
        assert '<li>mailsuite.com</li>' in html_content

        # Check ordered lists
        assert '<ol>' in html_content
        assert '<li>leadgenapp.io</li>' in html_content
        assert '<li>landofcoder.com</li>' in html_content

    def test_verify_special_characters_preserved(self, large_seo_summary_xml):
        """Test that special characters that would break XML are preserved."""
        result = xml_to_dict(large_seo_summary_xml, code_block_restore_group=-1)
        html_content = result['StructuredResponse']['InstantResponse']

        # These characters would break XML parsing without protection
        assert '<strong>' in html_content
        assert '</strong>' in html_content
        assert '<p>' in html_content
        assert '</p>' in html_content
        assert '<hr>' in html_content

        # Email addresses with @ symbol
        assert 'aliseo6170@gmail.com' in html_content
        assert 'priyanka.koyani@outreachdesk.com' in html_content

    def test_verify_emojis_preserved(self, large_seo_summary_xml):
        """Test that emoji characters are preserved in the HTML."""
        result = xml_to_dict(large_seo_summary_xml, code_block_restore_group=-1)
        html_content = result['StructuredResponse']['InstantResponse']

        # Check various emojis used in the content
        assert '📊' in html_content  # Overview
        assert '🔗' in html_content  # Guest Post
        assert '💰' in html_content  # Paid Link
        assert '🔄' in html_content  # Free Link
        assert '📋' in html_content  # Site Availability
        assert '🎯' in html_content  # SaaS Sites
        assert '👥' in html_content  # New Members
        assert '💼' in html_content  # Professional
        assert '🔑' in html_content  # Key Takeaways

    def test_verify_task_status_element(self, large_seo_summary_xml):
        """Test that sibling elements outside code block are parsed correctly."""
        result = xml_to_dict(large_seo_summary_xml)

        # TaskStatus should be a separate element
        assert result['StructuredResponse']['TaskStatus'] == 'Completed'

    def test_protection_disabled_would_fail(self, large_seo_summary_xml):
        """Verify that without protection, this large HTML causes parsing to fail."""
        # With protection disabled, the large HTML with XML-breaking characters
        # causes a ParseError due to mismatched tags
        # This test documents that protection is essential for this use case

        # Attempt to parse without protection should fail
        with pytest.raises(Exception):  # xml.etree.ElementTree.ParseError
            xml_to_dict(
                large_seo_summary_xml,
                protect_code_blocks=False,
                lenient_parsing=True
            )

        # With protection enabled, parsing succeeds
        result_protected = xml_to_dict(large_seo_summary_xml)

        # The protected version should have clean, predictable structure
        # The InstantResponse in protected version contains the full HTML block
        assert '```html' in result_protected['StructuredResponse']['InstantResponse']
        assert 'StructuredResponse' in result_protected
        assert result_protected['StructuredResponse']['TaskStatus'] == 'Completed'

    def test_large_content_performance(self, large_seo_summary_xml):
        """Test that protection handles large content efficiently."""
        import time

        start_time = time.time()
        result = xml_to_dict(large_seo_summary_xml)
        elapsed_time = time.time() - start_time

        # Should complete in reasonable time (< 1 second for this size)
        assert elapsed_time < 1.0

        # Verify result is complete
        assert 'StructuredResponse' in result
        assert len(result['StructuredResponse']['InstantResponse']) > 10000

    def test_count_html_elements(self, large_seo_summary_xml):
        """Test that all HTML elements are accounted for."""
        result = xml_to_dict(large_seo_summary_xml, code_block_restore_group=-1)
        html_content = result['StructuredResponse']['InstantResponse']

        # Count various element types
        assert html_content.count('<h1>') >= 1
        assert html_content.count('<h2>') >= 1
        assert html_content.count('<h3>') >= 5
        assert html_content.count('<h4>') >= 10
        assert html_content.count('<table') >= 2
        assert html_content.count('<ul>') >= 10
        assert html_content.count('<ol>') >= 1
        assert html_content.count('<li>') >= 100
        assert html_content.count('<p>') >= 10
        assert html_content.count('<strong>') >= 20

    def test_specific_pricing_data_accuracy(self, large_seo_summary_xml):
        """Test that specific pricing data is accurately preserved."""
        result = xml_to_dict(large_seo_summary_xml, code_block_restore_group=-1)
        html_content = result['StructuredResponse']['InstantResponse']

        # Verify specific pricing entries
        assert '$50-$60' in html_content  # dutable.com range
        assert '$300' in html_content     # techimply.com premium
        assert '$65' in html_content      # psychreg.org budget
        assert '$230' in html_content     # troopmessenger.com

        # Verify dollar signs aren't causing issues
        assert html_content.count('$') >= 50


class TestRealisticContentVariations:
    """Test variations of the realistic content."""

    def test_without_task_status(self):
        """Test HTML code block without additional sibling elements."""
        xml = '''<Response>
```html
<h1>Title & Content</h1>
<table>
<tr><td>A</td><td>B & C</td></tr>
</table>
```
</Response>'''

        result = xml_to_dict(xml, code_block_restore_group=-1)
        assert '<h1>Title & Content</h1>' in result['Response']
        assert '&' in result['Response']
        assert '<table>' in result['Response']

    def test_multiple_html_blocks_in_response(self):
        """Test multiple separate HTML code blocks."""
        xml = '''<MultiResponse>
<Section1>```html
<h1>Section 1</h1>
<p>Content with & symbol</p>
```</Section1>
<Section2>```html
<h2>Section 2</h2>
<div class="test">More & content</div>
```</Section2>
</MultiResponse>'''

        result = xml_to_dict(xml, code_block_restore_group=-1)
        assert '<h1>Section 1</h1>' in result['MultiResponse']['Section1']
        assert '<h2>Section 2</h2>' in result['MultiResponse']['Section2']
        assert '&' in result['MultiResponse']['Section1']
        assert '&' in result['MultiResponse']['Section2']


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
