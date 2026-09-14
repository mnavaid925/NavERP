"""Projects 7.9 — CollaborationCommunication forms sub-package (one module per entity).

Empty until Integrate. There is deliberately no ``ProjectNotifications`` module here: a
notification row is minted by a trigger (``msg_create``/``msg_edit``, the seeder, later 7.17's
rule engine) and closed by ``ntf_mark_read``, so it has no ModelForm and no create/edit route.
"""
