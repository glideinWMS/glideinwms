# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

FROM glideinwms/gwms-ci-el9
COPY entrypoint.sh /entrypoint.sh
RUN groupadd -g 115 glideinwms-ci
RUN useradd -u 1001 -g 115 glideinwms-ci
USER glideinwms-ci
ENTRYPOINT ["/entrypoint.sh"]
