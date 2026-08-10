// MongoDB Initialization Script
// Creates database, user, and initial admin account

// Switch to the application database
db = db.getSiblingDB('atech_noc');

// Create application user with read/write access
db.createUser({
  user: 'atech_app',
  pwd: 'atech_secure_password',
  roles: [
    { role: 'readWrite', db: 'atech_noc' }
  ]
});

// Create indexes for better performance
db.users.createIndex({ "email": 1 }, { unique: true });
db.devices.createIndex({ "ip_address": 1 });
db.devices.createIndex({ "status": 1 });
db.alerts.createIndex({ "created_at": -1 });
db.alerts.createIndex({ "status": 1 });
db.incidents.createIndex({ "created_at": -1 });
db.incidents.createIndex({ "status": 1 });
db.assets.createIndex({ "asset_tag": 1 }, { unique: true });
db.audit_logs.createIndex({ "created_at": -1 });
db.audit_logs.createIndex({ "user_id": 1 });

// Create default admin user
// Password: admin123 (bcrypt hash)
db.users.insertOne({
  id: "admin-" + new Date().getTime(),
  email: "admin@noc.com",
  name: "Admin User",
  password_hash: "$2b$12$R.8C9fyKXMjUZgTtMiS/ce4tvGmfH9mfNw0u1/yca1Yl3jFBi7TTm",
  role: "admin",
  is_active: true,
  created_at: new Date().toISOString()
});
db.users.insertOne({
  id: "admin-" + new Date().getTime(),
  email: "joy.mukherjee@ameyatechnologies.com",
  name: "Admin User",
  password_hash: "$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/X4.GQwOuLAFiQxA8.",
  role: "admin",
  is_active: true,
  created_at: new Date().toISOString()
});

print("Database initialized successfully!");
print("Default admin user created: admin@noc.com / admin123");
