FROM mambelli/gwms-ci-sl7
COPY entrypoint.sh /entrypoint.sh
RUN groupadd -g 115 glideinwms-ci
RUN useradd -u 1001 -g 115 glideinwms-ci
USER glideinwms-ci
ENTRYPOINT ["/entrypoint.sh"]
