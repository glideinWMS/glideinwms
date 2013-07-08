<!--
convert_frontend_2to3: an XSL transform to convert glideinWMS frontend v2
 configuration to v3.

To invoke (assuming the glideinwms source is in GLIDEIN_SRC):

xsltproc -o frontend-new.xml \
   $GLIDEIN_SRC/frontend/tools/convert_frontend_2to3.xslt \
   frontend.xml
-->

<xsl:transform version="1.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform">
<xsl:output method="xml" indent="yes"/>
<!-- Generic template: copy everything -->
<xsl:template match="node()|@*">
 <xsl:copy>
    <xsl:apply-templates select="node()|@*"/>
  </xsl:copy>
</xsl:template>

<!-- Specific templates -->
<!-- Remove downtimes node -->
<xsl:template match="downtimes"/>

<!-- Add process_logs to log_retention node and remove defaults -->
<xsl:template match="log_retention">
 <xsl:copy>
  <xsl:apply-templates select="node()"/>
<xsl:text>   </xsl:text> <process_logs>
<xsl:text>&#10;       </xsl:text> <process_log extension="info" max_days="7.0" max_mbytes="100.0" min_days="3.0" msg_types="INFO"/>
<xsl:text>&#10;       </xsl:text> <process_log extension="err" max_days="7.0" max_mbytes="100.0" min_days="3.0" msg_types="DEBUG,ERR,WARN"/>
<xsl:text>&#10;      </xsl:text> </process_logs>
<xsl:text>&#10;   </xsl:text>
 </xsl:copy>
</xsl:template>

<!-- Rename proxies element to credentials -->
<xsl:template match="proxies">
<credentials>
    <xsl:apply-templates select="@*|node()"/>
</credentials>
</xsl:template>

<!-- Rename proxy element to credential and add attributes -->
<xsl:template match="proxy">
<credential>
  <xsl:attribute name="type">grid_proxy</xsl:attribute>
  <xsl:attribute name="trust_domain">grid</xsl:attribute>
 <xsl:apply-templates select="@*|node()"/>
</credential>
</xsl:template>

</xsl:transform>
