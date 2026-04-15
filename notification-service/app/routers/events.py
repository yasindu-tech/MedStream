from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.schemas.notification import EventCreate, EventResponse, QueueStatusResponse
from app.services.notification_service import NotificationService
from app.models.notification import NotificationQueue
from sqlalchemy import select
from uuid import UUID

router = APIRouter()

"""
HOW OTHER SERVICES CALL THE NOTIFICATION SERVICE
-------------------------------------------------
Endpoint: POST http://notification-service:8007/api/notifications/events
No Authorization header needed (internal service call).

Example — appointment-service calling after booking:
  payload = {
      "event_type": "appointment.booked",
      "user_id": "uuid-of-patient",
      "payload": {
          "patient_name": "John Doe",
          "doctor_name": "Dr. Smith",
          "date": "2025-08-15",
          "time": "10:00 AM",
          "appointment_id": "uuid-of-appointment"
      },
      "channels": ["email", "in_app"],
      "priority": "normal"
  }
  response = requests.post(
      "http://notification-service:8007/api/notifications/events",
      json=payload
  )
"""

@router.post("/events", response_model=EventResponse)
async def create_event(event: EventCreate, db: AsyncSession = Depends(get_db)):
    service = NotificationService(db)
    notification_id = await service.handle_event(event)
    
    if not notification_id:
        # If duplicated or no templates found, we still return a successful receipt 
        # but with a special message if needed. Here we follow the contract.
        return {"notification_id": UUID(int=0), "status": "skipped"}
        
    return {"notification_id": notification_id, "status": "queued"}

@router.get("/queue/status/{queue_id}", response_model=QueueStatusResponse)
async def get_queue_status(queue_id: UUID, db: AsyncSession = Depends(get_db)):
    stmt = select(NotificationQueue).where(NotificationQueue.id == queue_id)
    result = await db.execute(stmt)
    item = result.scalar_one_or_none()
    
    if not item:
        raise HTTPException(status_code=404, detail="Queue item not found")
        
    return item
