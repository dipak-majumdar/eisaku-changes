# Enhanced Notification System Usage Guide

## Overview
The notification system has been enhanced to support real-time notifications with action buttons while maintaining backward compatibility with the existing system.

## Key Features

### ✅ Enhanced Features
- **Action Buttons**: Notifications can now have actionable buttons (Accept, Reject, Delete, etc.)
- **Deadlines**: Actions can have deadlines
- **Real-time Delivery**: Via existing WebSocket system
- **Bulk Operations**: Mark multiple notifications as read/delete
- **Enhanced Filtering**: Filter by action required, notification type, etc.
- **Action Tracking**: Track what actions were taken and when

### 🔧 Backward Compatibility
- All existing notification endpoints continue to work
- Existing WebSocket connections remain functional
- Legacy notification format is still supported

## API Endpoints

### Enhanced Notification Endpoints

#### Get Notifications with Filtering
```http
GET /api/v1/notifications/?page=1&size=20&action_required=true&notification_type=trip_approval
```

#### Get Notification Counts
```http
GET /api/v1/notifications/counts
```
Response:
```json
{
  "total": 25,
  "unread": 8,
  "pending_actions": 3
}
```

#### Create Notification with Actions
```http
POST /api/v1/notifications/
Content-Type: application/json

{
  "user_id": "550e8400-e29b-41d4-a716-446655440001",
  "notification_type": "trip_approval",
  "message": "Trip TRP001 requires your approval",
  "action_required": true,
  "action_type": "accept_reject",
  "action_data": {
    "trip_id": "TRP001",
    "action_url": "/trips/TRP001/approve"
  },
  "action_deadline": "2024-01-15T10:30:00Z"
}
```

#### Take Action on Notification
```http
POST /api/v1/notifications/{notification_id}/action
Content-Type: application/json

{
  "action": "accept",
  "action_data": {
    "notes": "Approved for immediate dispatch"
  }
}
```

#### Bulk Actions
```http
POST /api/v1/notifications/bulk-action
Content-Type: application/json

{
  "notification_ids": [
    "550e8400-e29b-41d4-a716-446655440001",
    "550e8400-e29b-41d4-a716-446655440002"
  ],
  "action": "mark_read"
}
```

## WebSocket Usage

### Connect to WebSocket
```javascript
const ws = new WebSocket(`ws://localhost:9000/api/v1/ws/ws?token=${jwtToken}`);

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  
  if (data.type === 'notification') {
    // Handle enhanced notification
    console.log('New notification:', data);
    
    if (data.action_required) {
      // Show action buttons
      showNotificationWithActions(data);
    } else {
      // Show regular notification
      showNotification(data);
    }
  }
};
```

### Enhanced Notification Format
```json
{
  "type": "notification",
  "notification_id": "550e8400-e29b-41d4-a716-446655440001",
  "notification_type": "trip_approval",
  "message": "Trip TRP001 requires your approval",
  "action_required": true,
  "action_type": "accept_reject",
  "created_at": "2024-01-10T08:30:00Z"
}
```

## Usage Examples

### Creating a Trip Approval Notification
```python
from services.notification_helpers import new_trip_created

await new_trip_created(
    session=session,
    user_id=manager_id,
    trip_id="UUID.randomUUID()",
    trip_code="TRP001",
    previous_status="draft",
    new_status="pending_approval",
    remarks="Trip created successfully",
    request=request,
    deadline_hours=24
)
```

### System-wide Notification
```python
from services.notification_helpers import notify_system

await notify_system(
    session=session,
    user_ids=[user1_id, user2_id, user3_id],
    message="Scheduled maintenance tonight at 11 PM",
    request=request,
    notification_type="system_maintenance"
)
```

## Action Handlers

The system includes built-in action handlers for:

### Trip Approval Handler
- **Actions**: `accept`, `reject`
- **Usage**: Trip approval workflows

### Vendor Approval Handler  
- **Actions**: `approve`, `reject`
- **Usage**: Vendor registration approval

### Complaint Handler
- **Actions**: `acknowledge`, `resolve`, `escalate`
- **Usage**: Customer complaint management

### Payment Handler
- **Actions**: `process`, `verify`
- **Usage**: Payment processing workflows

## Mobile App Integration

### React Native Example
```javascript
// Handle notification with actions
const handleNotification = (notification) => {
  if (notification.action_required) {
    Alert.alert(
      notification.message,
      'Choose an action:',
      [
        {
          text: 'Accept',
          onPress: () => takeAction(notification.notification_id, 'accept')
        },
        {
          text: 'Reject',
          onPress: () => takeAction(notification.notification_id, 'reject'),
          style: 'cancel'
        }
      ]
    );
  } else {
    // Show regular notification
    showToast(notification.message);
  }
};

const takeAction = async (notificationId, action) => {
  try {
    const response = await fetch(
      `/api/v1/notifications/${notificationId}/action`,
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({ action })
      }
    );
    
    const result = await response.json();
    console.log('Action result:', result);
  } catch (error) {
    console.error('Action failed:', error);
  }
};
```

## Migration Guide

### From Legacy System
1. **Database**: The notification table has been enhanced with new columns
2. **API**: All existing endpoints work unchanged
3. **WebSocket**: Existing connections continue to work
4. **Frontend**: Gradually add action button support

### New Columns in Notification Table
- `action_required` (boolean)
- `action_type` (string)
- `action_data` (JSON)
- `action_deadline` (datetime)
- `action_taken` (string)
- `action_taken_at` (datetime)

## Best Practices

1. **Use Action Handlers**: Leverage built-in action handlers for common workflows
2. **Set Deadlines**: Always set reasonable deadlines for actions
3. **Provide Context**: Include relevant data in `action_data`
4. **Handle Failures**: Always handle action failures gracefully
5. **Test Real-time**: Test WebSocket connections thoroughly
6. **Bulk Operations**: Use bulk actions for better performance

## Troubleshooting

### Common Issues

1. **Actions Not Working**: Check if action handlers are registered
2. **WebSocket Not Connecting**: Verify JWT token format
3. **Notifications Not Saving**: Check database connection
4. **Action Deadlines**: Ensure deadline format is ISO 8601

### Debug Mode
Enable debug logging:
```python
import logging
logging.getLogger('services.notification').setLevel(logging.DEBUG)
logging.getLogger('core.websocket_manager').setLevel(logging.DEBUG)
```
