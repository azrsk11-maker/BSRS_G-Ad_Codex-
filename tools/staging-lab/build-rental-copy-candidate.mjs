// Derive the exact reviewed two-literal change inside the disposable lab image.
import {createHash} from 'node:crypto';
import {readFileSync, writeFileSync} from 'node:fs';

const [template] = process.argv.slice(2);
const digest = value => createHash('sha256').update(value).digest('hex');
const source = readFileSync(template, 'utf8');
if (digest(source) !== '2ce5c621017bc46db8971554b890a8f3c29bacfd02b8d7d379d38c67f77d8fd6') {
  throw new Error('Unexpected rental fixture source');
}
const candidate = source
  .replace('Immediate rental enquiries are the priority for this campaign. Choose your actual move-in timeline so the team can understand your situation.',
    'Choose when you need to move so we can review your rental requirements against your timeline.')
  .replace('This preview form cannot send without JavaScript and a connected service. Please call +971 56 828 5677 or use WhatsApp.',
    'To send an online enquiry, JavaScript is required. You can also use the contact options on this page.');
if (digest(candidate) !== '43632b26204bb898fffc36381726f895f76ee57df417aadffe0b7d07f89bd868') {
  throw new Error('Unexpected rental fixture candidate');
}
writeFileSync(template, candidate);
