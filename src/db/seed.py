import os
import sys
from pathlib import Path

# Add project root (where src/ is) to PYTHONPATH
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.append(BASE_DIR.__str__())


import json
from uuid import uuid4
from sqlmodel import Session, select, delete
from passlib.context import CryptContext

from db.session import engine
from models import *
from core.config import (
    SU_FIRST_NAME, SU_LAST_NAME, SU_USERNAME, SU_EMAIL, SU_MOBILE, SU_PASSWORD
)


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Load permissions from JSON file


def seed_permission():
    PERMISSIONS_FILE = os.path.join(BASE_DIR.__str__(), 'permissions.json')

    with open(PERMISSIONS_FILE, 'r') as file:
        ROLE_PERMISSIONS = json.load(file)[0]

    with Session(engine) as session:
        for role_name, models in ROLE_PERMISSIONS.items():
            # ensure role exists
            role = session.exec(select(Role).where(Role.name == role_name)).first()

            if not role:
                role = Role(id=uuid4(), name=role_name, description=f"{role_name} role")
                session.add(role)
                session.commit()

            # Clear existing RolePermission links once per role
            session.exec(delete(RolePermission).where(RolePermission.role_id == role.id))
            session.commit()

            # Loop over models
            for model_name, perms in models.items():
                for perm_name, perm_info in perms.items():
                    # Ensure permission exists
                    existing_perm = session.exec(
                        select(Permission).where(
                            Permission.model_name == model_name,
                            Permission.action_name == perm_name,
                        )
                    ).first()

                    if not existing_perm:
                        existing_perm = Permission(
                            id=uuid4(),
                            model_name=model_name,
                            action_name=perm_name,
                        )
                        session.add(existing_perm)
                        session.commit()
                        session.refresh(existing_perm)

                    # Link role and permission in RolePermission
                    role_perm = RolePermission(
                        role_id=role.id,
                        permission_id=existing_perm.id,
                        required=str(perm_info).lower() in ("true",)
                    )
                    session.add(role_perm)

        # Commit all new role-permission links for this role
        session.commit()
    print("✅ Permissions seeded successfully")


def seed_admin():
    with Session(engine) as session:
        # 1. Check if role exists
        admin_role = session.exec(select(Role).where(Role.name == "admin")).first()
        if not admin_role:
            admin_role = Role(id=uuid4(), name="admin", description="Administrator Role Description")
            session.add(admin_role)
            session.commit()
            session.refresh(admin_role)

        # 2. Create admin user if not exists
        admin_user = session.exec(select(User).where(User.email == SU_EMAIL)).first()
        if not admin_user:
            admin_user = User(
                id=uuid4(),
                email=SU_EMAIL,
                username=SU_USERNAME,
                first_name=SU_FIRST_NAME,
                last_name=SU_LAST_NAME,
                mobile=SU_MOBILE,
                hashed_password=pwd_context.hash(SU_PASSWORD),  
                is_active=True,
                role_id=admin_role.id,
            )
            session.add(admin_user)
            session.commit()

        print("✅ Admin role & user seeded successfully")


def seed_locations():
    with Session(engine) as session:
        # Seed Country
        country = session.exec(select(Country).where(Country.name == "India")).first()
        if not country:
            country = Country(id=uuid4(), name="India", code="IN")
            session.add(country)
            session.commit()
            session.refresh(country)

        # Seed State
        state = session.exec(select(State).where(State.name == "West Bengal")).first()
        if not state:
            state = State(id=uuid4(), name="West Bengal", code="WB", country_id=country.id)
            session.add(state)
            session.commit()
            session.refresh(state)

        # Seed District
        district = session.exec(select(District).where(District.name == "Howrah")).first()
        if not district:
            district = District(id=uuid4(), name="Howrah", state_id=state.id)
            session.add(district)
            session.commit()
            session.refresh(district)

        # Seed City
        city = session.exec(select(City).where(City.name == "Dankuni")).first()
        if not city:
            city = City(id=uuid4(), name="Dankuni", district_id=district.id)
            session.add(city)
            session.commit()
            session.refresh(city)
        
        print("✅ Locations seeded successfully")


def seed_regions():
    with Session(engine) as session:
        # Seed Region
        data = ['North', 'South', 'East', 'West', 'Central']
        for region_name in data:
            region = session.exec(select(Region).where(Region.name == region_name)).first()
            if not region:
                region = Region(id=uuid4(), name=region_name)
                session.add(region)
        
        session.commit()
        print("✅ Regions seeded successfully")



if __name__ == "__main__":
    seed_permission()
    seed_admin()
    seed_locations()
    seed_regions()
