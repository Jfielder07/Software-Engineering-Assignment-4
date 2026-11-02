"""Create a fictional demo staff account from the CLI, not from the public website."""
import argparse
import getpass
from database_connection import DatabaseConnection
from authentication_service import AuthenticationService
from staff_repository import StaffRepository
from staff import Role

p = argparse.ArgumentParser()
p.add_argument('--database', default='prs_web.db')
p.add_argument('--username', required=True)
p.add_argument('--role', choices=['doctor', 'clinical_staff'], required=True)
a = p.parse_args()
password = getpass.getpass('New password (12+ characters): ')
with DatabaseConnection(a.database) as db:
    staff = AuthenticationService(StaffRepository(db)).register_staff(a.username, password, Role(a.role), bootstrap=True)
    print('Account created:', staff.username, staff.role.value)
