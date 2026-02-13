from uuid import UUID
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import Session, select, func
from fastapi import HTTPException, Request, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy import delete
from sqlalchemy.orm import selectinload

from core import messages
from models import Role as Model, RolePermission
from models.permission import Permission
from schemas import (
    RoleList as ListSchema, 
    RolePermissionRead as ReadSchema, 
    PermissionReadWithRequired
)
from schemas.role import ActiveRoleList


OBJECT_NOT_FOUND = messages.ROLE_NOT_FOUND
OBJECT_EXIST = messages.ROLE_EXIST
OBJECT_DELETED = messages.ROLE_DELETED


class Service:
    role_hierarchy = {
        "admin": [],  # admin sees all
        "management": ["admin","management"],  # management sees all except none excluded here
        "accountant": ["admin","management","accountant"],  
        "corporate admin": ["admin", "management","corporate admin"],
        "national manager": ["admin", "management","corporate admin", "national manager","accountant"],  
        "regional manager": ["admin", "management", "corporate admin", "national manager", "customer", "vendor","regional manager","accountant"],
        "branch manager": ["admin", "management", "corporate admin", "national manager", "regional manager","branch manager","accountant"],
        "field executive": ["field executive", "supervisor", "supplier lead","branch manager"],  
        "supervisor": ["field executive", "supervisor", "supplier lead"],  
        "supplier lead": ["field executive", "supervisor", "supplier lead"],  
        "customer": [],  
        "vendor": []  
    }

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_object(self, id: UUID) -> Model:
        result = await self.session.execute(
            select(Model)
            .options(selectinload(Model.role_permissions).selectinload(RolePermission.permission))
            .where(Model.id == id)
        )
        obj = result.scalars().first()
        if not obj:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, 
                detail=OBJECT_NOT_FOUND
            )
        return obj
    
    async def _save(self, obj: Model) -> Model:
        """Utility: add + commit + refresh"""
        try:
            self.session.add(obj)
            await self.session.commit()
            await self.session.refresh(obj)
            return obj
        except IntegrityError as e:
            self.session.rollback()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=OBJECT_EXIST,
            )

    async def _paginate(self, query, request: Request, page=1, size=10) -> ListSchema:
        count_query = select(func.count()).select_from(query.subquery())
        total = (await self.session.execute(count_query)).scalar()
        
        offset = (page - 1) * size
        result = await self.session.execute(query.offset(offset).limit(size))
        results = result.unique().scalars().all()

        next_url = (
            str(request.url.include_query_params(page=page + 1))
            if offset + size < total else None
        )
        previous_url = (
            str(request.url.include_query_params(page=page - 1))
            if page > 1 else None
        )

        return ListSchema(total=total, next=next_url, previous=previous_url, results=results)

    async def list(self, request: Request, page=1, size=10, search: str | None = None) -> ListSchema:
        query = select(Model)

        # ✅ Apply search filter
        if search:
            query = query.where(Model.name.ilike(f"%{search}%"))
        
        # ✅ Add ordering for consistent results
        query = query.order_by(Model.created_at.desc())
            
        return await self._paginate(query, request, page, size)
    
    async def active_list(self, request: Request, search: str | None = None) -> ActiveRoleList:
        current_user_role_name = None
        current_user = getattr(request.state, "user", None)
        if current_user and current_user.role and current_user.role.name:
            current_user_role_name = current_user.role.name.lower()

        query = select(Model).where(Model.is_active)

        # Determine which roles to exclude based on current user role
        exclude_roles = []
        if current_user_role_name and current_user_role_name in self.role_hierarchy:
            exclude_roles = self.role_hierarchy[current_user_role_name]

        if exclude_roles:
            query = query.where(~Model.name.in_(exclude_roles))

        if search:
            query = query.where(Model.name.ilike(f"%{search}%"))

        result = await self.session.execute(query.order_by(Model.name))
        results = result.unique().scalars().all()
        return ActiveRoleList(results=results)

    async def read(self, request: Request, id: UUID) -> ReadSchema:
        obj = await self.get_object(id)
        
        # Map permissions with required from RolePermission
        permissions = [
            PermissionReadWithRequired(
                id=rp.permission.id,
                model_name=rp.permission.model_name,
                action_name=rp.permission.action_name,
                description=rp.permission.description,
                required=rp.required,   # 👈 works now
            )
            for rp in obj.role_permissions
        ]
        
        return ReadSchema(
            id=obj.id,
            name=obj.name,
            description=obj.description,
            is_active=obj.is_active,
            created_at=obj.created_at,
            updated_at=obj.updated_at,
            created_by=obj.created_by,
            updated_by=obj.updated_by,
            permissions=permissions,
        )

    async def create(self, request: Request, item: Model): 
        user = request.state.user
        permissions = item.permissions or []
        
        # Create the role
        obj = Model(
            name=item.name, 
            description=item.description or '', 
            created_by=user.id, 
            updated_by=user.id
        )
        obj = await self._save(obj)
        
      
        result = await self.session.execute(select(Permission))
        all_permissions = result.unique().scalars().all()
        
      
        sent_permission_ids = {perm.id for perm in permissions}
        
      
        for system_perm in all_permissions:
            if system_perm.id in sent_permission_ids:
      
                frontend_perm = next(p for p in permissions if p.id == system_perm.id)
                required = frontend_perm.required
            else:
      
                required = False
            
            self.session.add(RolePermission(
                role_id=obj.id,
                permission_id=system_perm.id,
                required=required
            ))
        
        await self.session.commit()
        
        # ✅ Re-fetch object with relationships for response
        return await self.get_object(obj.id)


    async def update(self, request: Request, id: UUID, item: Model):
        user = request.state.user
        obj = await self.get_object(id)
        permissions = item.permissions or []
        
       
        if item.name is not None:
            obj.name = item.name
        if item.description is not None: 
            obj.description = item.description
        
        
        obj.updated_by = user.id
        obj.updated_at = datetime.utcnow()
        
        obj = await self._save(obj)
        
        # Clear old permissions
        await self.session.execute(
            delete(RolePermission).where(RolePermission.role_id == id)
        )
        
       
        result = await self.session.execute(select(Permission))
        all_permissions = result.unique().scalars().all()
        
      
        sent_permission_ids = {perm.id for perm in permissions}
        
      
        for system_perm in all_permissions:
            if system_perm.id in sent_permission_ids:
          
                frontend_perm = next(p for p in permissions if p.id == system_perm.id)
                required = frontend_perm.required
            else:
              
                required = False
            
            self.session.add(RolePermission(
                role_id=obj.id,
                permission_id=system_perm.id,
                required=required
            ))
        
        await self.session.commit()
        
        # ✅ Re-fetch object with relationships for response
        return await self.get_object(obj.id)

    async def delete(self, request: Request, id: UUID):
        obj = await self.get_object(id)
        await self.session.delete(obj)
        await self.session.commit()
        return {"detail": OBJECT_DELETED}
    
    async def toggle_active(self, request: Request, id: UUID):
        user = request.state.user
        obj = await self.get_object(id)
        
        # ✅ Update only the is_active, updated_by, updated_at field
        obj.is_active = not obj.is_active
        obj.updated_by = user.id
        obj.updated_at = datetime.utcnow()

        return await self._save(obj)

    async def branch_roles_list(self, request: Request, branch_id: UUID | None = None) -> ActiveRoleList:
        """
        Get roles for branch employee creation context.
        If branch_id provided: return only Field Executive, Supervisor, Supplier Lead
        If no branch_id: return all active roles
        """
        query = select(Model).where(Model.is_active)
        
        # ✅ If branch_id provided, filter to specific roles
        if branch_id:
            allowed_role_names = ["field executive", "supervisor", "supplier lead"]
            query = query.where(Model.name.in_(allowed_role_names))
        
        result = await self.session.execute(query.order_by(Model.name))
        results = result.unique().scalars().all()
        return ActiveRoleList(results=results)
