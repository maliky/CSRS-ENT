FROM odoo:19.0-20260723@sha256:e415f9924395e7521245813135112f264b9222bcde3b1d3c2ee9ff073081540a

USER root

COPY --chown=odoo:odoo infrastructure/compose/odoo/image/odoo.conf /etc/odoo/odoo.conf
COPY --chown=odoo:odoo apps/odoo/addons /mnt/extra-addons
COPY --chmod=0755 infrastructure/compose/odoo/image/bootstrap.sh /usr/local/bin/pent-odoo-bootstrap
COPY --chmod=0755 infrastructure/compose/odoo/image/runtime.sh /usr/local/bin/pent-odoo-runtime

USER odoo

EXPOSE 8069 8072
CMD ["/usr/local/bin/pent-odoo-runtime", "server"]
