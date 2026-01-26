#!/usr/bin/env bash
export LC_ALL=C
set -e -o pipefail

GPG="gpg2"
gpg_key_name=FD9A772C7300F4C894D1A819FE50480862E6451C

rm *.asc || true
rm SHA256SUMS || true
rm SHA256SUMS.asc || true

### signed hashes

for file in *.zip *.tar.gz *.dmg; do
  if [ -f "$file" ]; then
    # Sign the file using gpg2
    LANG=en_US ${GPG} --armor --detach-sign "$file"
    echo "Signed $file"

    sha256sum "$file" | awk '{print $1 "  " $2}' >> SHA256SUMS
  fi
done

LANG=en_US ${GPG} --clearsign \
        --digest-algo sha256 \
        --local-user "$gpg_key_name" \
        --armor \
        --output SHA256SUMS.asc SHA256SUMS

### virustotal table

rm virustotal.txt || true
input="SHA256SUMS"

echo "**Checksum & VirusTotal Analysis:**" > virustotal.txt
echo " " >> virustotal.txt
echo "| Link   | SHA256      |" >> virustotal.txt
echo "|--------|-------------|" >> virustotal.txt

while read -r line
do
  commit_hash=$(echo $line | cut -d" " -f1)
  file_name=$(echo $line | cut -d" " -f2)
  echo '| '"[${file_name}](https://www.virustotal.com/gui/file/${commit_hash})" '| `'"${commit_hash}"'` |' >> virustotal.txt

done < "$input"

echo -e "\n" >> virustotal.txt
echo "This release was signed by https://keybase.io/deckersu (GPG fingerprint: \`FD9A 772C 7300 F4C8 94D1 A819 FE50 4808 62E6 451C\`)." >> virustotal.txt

rm SHA256SUMS || true


