"""Synthetic all-role permission and first-ever qualification boundaries; no upload."""
import copy
from contextlib import redirect_stdout
from datetime import timedelta
import io
from pathlib import Path
import tempfile
import unittest
import source_queue as source
from test_source_queue import fixture, snapshot, NOW, OID

ROLES=('off_plan','resale','tenant','seller','landlord')


def role_fixture(role):
    parts=fixture()
    parts[0]['records'][0]['role']=role
    parts[0]['intake'][0]['role']=role
    if role in ('seller','landlord'):
        parts[0]['records'][0]['authority_confirmed']=True
    return parts


class RolePermissionMatrixTests(unittest.TestCase):
    def projection(self, parts):
        with tempfile.TemporaryDirectory(prefix='bsre-synthetic-role-') as temp:
            with source.PrivateQueue(Path(temp)/'synthetic.sqlite') as queue:
                item=snapshot(parts)
                staged=queue.stage(item,NOW)
                queue.mark_reviewed(OID,staged['snapshot_sha256'],'SYNTHETIC-OWNER-REVIEW',NOW)
                return queue.projection(item,NOW+timedelta(seconds=1))

    def test_all_five_roles_preserve_original_identity_and_private_only_boundary(self):
        for role in ROLES:
            with self.subTest(role=role):
                parts=role_fixture(role)
                result=self.projection(parts)
                self.assertTrue(result['UPLOAD_PROHIBITED'])
                self.assertFalse(result['google_source_format_verified'])
                self.assertEqual(len(result['rows']),1)
                row=result['rows'][0]
                self.assertEqual(set(row),{'outcome_id','lead_id','original_gclid','actual_qualified_at_utc','conversion_action_id','conversion_name','original_order_id','private_review_valid_until_utc'})
                self.assertEqual(row['original_gclid'],parts[0]['records'][0]['click_id'])
                self.assertEqual(row['actual_qualified_at_utc'],parts[0]['records'][0]['occurred_at_utc'])
                self.assertEqual(result['summary']['network_calls'],0)

    def test_all_five_roles_refusal_and_test_exclusion(self):
        for role in ROLES:
            for change in ('refused','test'):
                with self.subTest(role=role,change=change):
                    parts=role_fixture(role)
                    if change=='refused':parts[1][0]['ad_measurement']=False
                    else:
                        parts[0]['records'][0]['is_test']=True
                        parts[0]['intake'][0]['is_test']=True
                    with tempfile.TemporaryDirectory(prefix='bsre-synthetic-hold-') as temp:
                        with source.PrivateQueue(Path(temp)/'synthetic.sqlite') as queue:
                            item=snapshot(parts);queue.stage(item,NOW)
                            self.assertEqual(queue.projection(item,NOW)['rows'],[])

    def test_no_role_regrant_after_withdrawal(self):
        for role in ROLES:
            with self.subTest(role=role):
                parts=role_fixture(role)
                original=copy.deepcopy(parts[1][0])
                original['withdrawn_at_utc']='2026-11-02T08:00:00Z'
                parts[1][0].update(evidence_id='SYNTHETIC-REGRANT',observed_at_utc='2026-11-03T08:00:00Z')
                parts[1].append(original)
                with tempfile.TemporaryDirectory(prefix='bsre-synthetic-withdrawal-') as temp:
                    with source.PrivateQueue(Path(temp)/'synthetic.sqlite') as queue:
                        item=snapshot(parts);staged=queue.stage(item,NOW)
                        self.assertIn('WITHDRAWAL_REVIEW_HOLD',staged['hold_counts'])
                        self.assertEqual(queue.projection(item,NOW)['rows'],[])

    def test_contact_fields_rejected_for_every_role(self):
        for role in ROLES:
            for target in ('ledger','purpose'):
                with self.subTest(role=role,target=target):
                    parts=role_fixture(role)
                    row=parts[0]['records'][0] if target=='ledger' else parts[1][0]
                    row['email']='SYNTHETIC_CONTACT_NEVER_EXPORT@example.invalid'
                    with self.assertRaises((source.SourceError,ValueError)) as caught:
                        snapshot(parts).evaluate(NOW)
                    self.assertNotIn('SYNTHETIC_CONTACT',str(caught.exception))

    def test_contact_rejection_preserves_existing_private_review(self):
        for role in ROLES:
            with self.subTest(role=role), tempfile.TemporaryDirectory(prefix='bsre-synthetic-preserve-') as temp:
                path=Path(temp)/'synthetic.sqlite'
                parts=role_fixture(role)
                with source.PrivateQueue(path) as queue:
                    item=snapshot(parts);stage=queue.stage(item,NOW)
                    queue.mark_reviewed(OID,stage['snapshot_sha256'],'SYNTHETIC-REVIEW',NOW)
                    before=path.read_bytes()
                    parts[0]['records'][0]['phone']='SYNTHETIC_CONTACT_NEVER_STORE'
                    with self.assertRaisesRegex(source.SourceError,'OUTCOME_EXTRACT_FIELDS_INVALID'):
                        queue.stage(snapshot(parts),NOW+timedelta(seconds=1))
                    self.assertEqual(path.read_bytes(),before)
                    self.assertEqual(len(queue.projection(item,NOW+timedelta(seconds=2))['rows']),1)

    def test_cli_rejects_contact_extract_before_creating_database(self):
        with tempfile.TemporaryDirectory(prefix='bsre-synthetic-cli-') as temp:
            root=Path(temp); parts=fixture()
            parts[0]['records'][0]['phone']='SYNTHETIC_CONTACT_NEVER_STORE'
            item=snapshot(parts)
            args=['stage','--db',str(root/'never-created.sqlite'),'--now',NOW.isoformat()]
            for name,raw in item.values.items():
                path=root/(name+'.json')
                path.write_text(source.canonical(raw),encoding='utf-8',newline='\n')
                args.extend(['--'+name,str(path)])
            capture=io.StringIO()
            with redirect_stdout(capture):self.assertEqual(source.main(args),2)
            self.assertIn('OUTCOME_EXTRACT_FIELDS_INVALID',capture.getvalue())
            self.assertNotIn('SYNTHETIC_CONTACT',capture.getvalue())
            self.assertNotIn(str(root),capture.getvalue())
            self.assertFalse((root/'never-created.sqlite').exists())


if __name__=='__main__': unittest.main()
