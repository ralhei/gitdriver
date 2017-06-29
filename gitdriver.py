#!/usr/bin/python

import os
import sys
import argparse
import subprocess

import yaml

from drive import GoogleDrive, DRIVE_RW_SCOPE


MIME_TYPE_EXTENSIONS = {
    'text/plain': u'txt',
    'text': u'txt',
    'text/html': u'html',
    'html': u'html',
    'application/vnd.oasis.opendocument.text': u'odt',
    'application/pdf': u'pdf'
}


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument('--config', '-f', default='gd.conf')
    p.add_argument('--text', '-T', action='store_const', const='text/plain', dest='mime_type')
    p.add_argument('--html', '-H', action='store_const', const='text/html', dest='mime_type')
    p.add_argument('--pdf', '-P', action='store_const', const='application/pdf', dest='mime_type')
    p.add_argument('--odt', '-O', action='store_const', const='application/vnd.oasis.opendocument.text', dest='mime_type')
    p.add_argument('--mime-type', dest='mime_type')
    p.add_argument('--raw', '-R', action='store_true', help='Download original document if possible.')
    p.add_argument('docid')

    return p.parse_args()


def main():
    opts = parse_args()
    if not opts.mime_type:
        print("Exactly one mime-type must be given!")
        exit(1)
    cfg = yaml.load(open(opts.config))
    gd = GoogleDrive(
        client_id=cfg['googledrive']['client id'],
        client_secret=cfg['googledrive']['client secret'],
        scopes=[DRIVE_RW_SCOPE],
    )

    # Establish our credentials.
    gd.authenticate()

    # Get information about the specified file.  This will throw
    # an exception if the file does not exist.
    md = gd.get_file_metadata(opts.docid)

    # Precalc some directory and filename constants:
    extension = filetype = MIME_TYPE_EXTENSIONS[opts.mime_type]
    gitrepo = u'%s/%s' % (filetype, md['title'])
    filename = u'content.%s' % extension

    if os.path.exists(gitrepo):
        sys.stderr.write('Error: repo "%s" already exists.\n' % gitrepo)
        sys.exit(1)

    # Initialize the git repository.
    print('Create repository %s' % gitrepo)
    subprocess.call(['git', 'init', gitrepo])
    os.chdir(gitrepo)

    # Iterate over the revisions (from oldest to newest).
    for rev in gd.revisions(opts.docid):
        with open(filename, 'w') as fd:
            if 'exportLinks' in rev and not opts.raw:
                # If the file provides an 'exportLinks' dictionary,
                # download the requested MIME type.
                r = gd.session.get(rev['exportLinks'][opts.mime_type])
            elif 'downloadUrl' in rev:
                # Otherwise, if there is a downloadUrl, use that.
                r = gd.session.get(rev['downloadUrl'])
            else:
                raise KeyError('unable to download revision')

            # Write file content into local file.
            for chunk in r.iter_content():
                fd.write(chunk)

        # Commit changes to repository.
        subprocess.call(['git', 'add', filename])
        subprocess.call(
            ['git', 'commit',
             '-m', 'url: %s' % rev['selfLink'],
             '--author="%s <%s>"' % (rev['lastModifyingUser']['displayName'],
                                     rev['lastModifyingUser']['emailAddress']),
             '--date="%s"' % rev['modifiedDate']
             ])


if __name__ == '__main__':
    main()
