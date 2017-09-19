#!/usr/bin/env python
""" Simple script to automate backing up everything relating to a wordpress website """
from __future__ import print_function
import argparse
import subprocess
import os
import re
from string import Template
import tempfile
import datetime
import shutil
import logging


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger()


def simple_run(cmd_line_args):
    """ Run a command-line program, and return the output """
    logger.debug('Invoking command line: {}'.format(cmd_line_args))
    p = subprocess.Popen(cmd_line_args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, err = p.communicate()
    if err:
        logger.debug('Error output received: {}'.format(err[:100]))
        raise Exception('Error running {}: {}'.format(cmd_line_args[0] if len(cmd_line_args) > 0 else '(unspecified)', err))
    return out


def sql_safe(val, valid_regex = re.compile('^[A-Za-z0-9_]*$')):
    """ Pessimistic function to return a SQL-safe version of a string. Throw an error if it isn't already safe... """
    if not valid_regex.match(val):
        raise Exception('The value {} is not database-safe'.format(val))
    return val
    

def get_tables_with_prefix(schema, prefix, settings_file='my.cnf'):
    """ Get a list of tables in the schema with the right prefix (using mysql command line at this point) """
    table_sql = "select table_name from information_schema.tables where table_schema = '{}'".format(sql_safe(schema))
    if prefix:
        table_sql += " and table_name like '{}%'".format(sql_safe(prefix))
    logger.debug('SQL to obtain table list: ' + table_sql)
    get_tables_args = ['mysql', '--defaults-extra-file=' + settings_file, '-B', '-N', '-e', table_sql]
    output = simple_run(get_tables_args)
    return [tbl for tbl in output.split('\n') if len(tbl) >= 1]


def parse_wordpress_config(wordpress_dir, 
                           settings_regex = re.compile("^(?:define\('([^']*)'\s*,\s*'([^']*)'\))|(?:\$(.*?)\s*=\s*'(.*?)')")):
    """ Pull interesting settings out of the wp-config file in the wordpress directory """
    config_file = os.path.join(wordpress_dir, 'wp-config.php')
    logger.debug("Parsing config file {}".format(config_file))
    matches = (settings_regex.match(line) for line in open(config_file, 'r'))
    info = ((m.group(1), m.group(2)) if m.group(1) else (m.group(3), m.group(4)) for m in matches if m)
    return {k: v for k, v in info}


class MySQLConfig(object):
    """ Given a ConfigFileParser object, write a file that mysql command line programmes can use """
    def write_config(self):
        """ Write the settings file """
        logger.debug('Writing MySQL config file: {}'.format(self.temp_file.name))
        f = self.temp_file.file
        print("[client]", file=f)
        for k, v in {'host': self.config['DB_HOST'], 'user': self.config['DB_USER'], 'password': self.config['DB_PASSWORD']}.iteritems():
            print("{} = {}".format(k, v), file=f)
        f.close()

    def __init__(self, settings_dict):
        self.temp_file = tempfile.NamedTemporaryFile()
        self.config = settings_dict
        self.write_config()

    def get_path(self):
        return self.temp_file.name


def do_work(args):
    """ Do the work of backing everything up, based on the passed-in arguments """

    # Pull out WordPress/MySQL settings, and set up a settings file that is used for command-line use
    settings_dict = parse_wordpress_config(args.wordpress_dir)
    mysql_settings = MySQLConfig(settings_dict)

    # Find out the tables we need to back up
    table_list = get_tables_with_prefix(settings_dict['DB_NAME'], settings_dict['table_prefix'], mysql_settings.get_path())

    # Start dumping files in a temp directory, ready for archiving
    temp_dir = tempfile.mkdtemp()
    try:
        # First, back up MySQL into a file here...
        logger.info("Backing up MySQL database as {}".format(args.mysql_archive))
        backup_args = ['mysqldump', '--defaults-extra-file=' + mysql_settings.get_path(), '--add-drop-table', settings_dict['DB_NAME']] + table_list
        out = simple_run(backup_args)
        with open(os.path.join(temp_dir, args.mysql_archive), 'w') as f:
            print(out, file=f)

        # Next, tar up the wordpress directory itself
        logger.info("Backing up wordpress directory as {}".format(args.wordpress_archive))
        tar_args = ['tar', 'cvfz', os.path.join(temp_dir, args.wordpress_archive), '-C', args.wordpress_dir, '.']
        simple_run(tar_args)

        # Finally, create the master backup file
        timestamp = datetime.datetime.now().strftime('%y%m%d%H%M%S')
        master_backup_file = os.path.expanduser(os.path.join(args.output_dir, "{}_{}.tar.gz".format(args.site_name, timestamp)))

        cmd_line = ['tar', 'cvfz', master_backup_file, '-C', temp_dir, args.mysql_archive, args.wordpress_archive]
        logger.info('Combining archives into single file {}'.format(master_backup_file))
        simple_run(cmd_line)
    finally:
        # Finally, remove the directory
        logger.debug('Tidying up temporary directory {}'.format(temp_dir))
        shutil.rmtree(temp_dir)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description = "Back up WordPress directory and MySQL database into a single tar archive")
    parser.add_argument('site_name', default='wordpress')
    parser.add_argument('-o', '--output_dir', required=False, default='~/backup', help="Directory into which backup archive should be placed")
    parser.add_argument('-l', '--log_level', required=False, default='INFO', help="Logging level (useful for debugging)")
    parser.add_argument('-m', '--mysql_archive', required=False, default='mysqldmp.sql', help="Name of mysql component file within backup")
    parser.add_argument('-w', '--wordpress_archive', required=False, default='wordpress.tar.gz', help="Name of wordpress component within backup")
    parser.add_argument('wordpress_dir', default='.')
    args = parser.parse_args()

    logger.setLevel(logging.getLevelName(args.log_level.upper()))

    do_work(args)


