# Database Migration Guide

This project supports both SQLite (development) and PostgreSQL (production) databases with automatic fallback configuration.

## Current Configuration

The project uses a flexible database configuration that:
- Defaults to SQLite for development
- Supports PostgreSQL for production
- Automatically falls back to SQLite if PostgreSQL dependencies are not available

## Development Setup (SQLite)

SQLite is the default and requires no additional setup:

```bash
# Current configuration in .env
DATABASE_URL=sqlite:///db.sqlite3
```

To use SQLite with a custom path:
```bash
DATABASE_URL=sqlite:///path/to/your/database.sqlite3
```

## Production Setup (PostgreSQL)

### 1. Install PostgreSQL

**On Ubuntu/Debian:**
```bash
sudo apt-get install postgresql postgresql-contrib
sudo apt-get install python3-dev libpq-dev
```

**On CentOS/RHEL:**
```bash
sudo yum install postgresql postgresql-server postgresql-devel
sudo yum install python3-devel
```

**On Arch Linux:**
```bash
sudo pacman -S postgresql postgresql-libs
```

### 2. Install Python PostgreSQL Adapter

```bash
pip install psycopg2-binary==2.9.9
```

### 3. Configure PostgreSQL

**Initialize PostgreSQL (if first time):**
```bash
sudo postgresql-setup initdb
sudo systemctl start postgresql
sudo systemctl enable postgresql
```

**Create database and user:**
```bash
sudo -u postgres psql
```

In PostgreSQL shell:
```sql
CREATE DATABASE agenty;
CREATE USER agenty_user WITH PASSWORD 'your_secure_password';
GRANT ALL PRIVILEGES ON DATABASE agenty TO agenty_user;
ALTER USER agenty_user CREATEDB;  -- For running tests
\q
```

### 4. Update Environment Variables

Update your `.env` file for production:

```bash
# PostgreSQL configuration
DATABASE_URL=postgres://agenty_user:your_secure_password@localhost:5432/agenty

# Production settings
DJANGO_DEBUG=False
DJANGO_ALLOWED_HOSTS=your-domain.com,www.your-domain.com
```

## Migration Process

### From SQLite to PostgreSQL

1. **Backup current SQLite data:**
   ```bash
   python manage.py dumpdata --settings=core.settings_dev > backup.json
   ```

2. **Update environment to PostgreSQL:**
   ```bash
   # Update .env file
   DATABASE_URL=postgres://agenty_user:password@localhost:5432/agenty
   ```

3. **Run migrations on PostgreSQL:**
   ```bash
   python manage.py migrate --settings=core.settings_prod
   ```

4. **Load data (optional):**
   ```bash
   python manage.py loaddata backup.json --settings=core.settings_prod
   ```

### Testing Database Configuration

```bash
# Test development settings (SQLite)
python manage.py check --settings=core.settings_dev

# Test production settings (PostgreSQL)
python manage.py check --settings=core.settings_prod
```

## Database Configuration Files

- `core/database_config.py` - Database configuration utility
- `core/settings_dev.py` - Development settings (SQLite)
- `core/settings_prod.py` - Production settings (PostgreSQL)

## Troubleshooting

### Common Issues

1. **psycopg2 installation fails:**
   - Ensure PostgreSQL development libraries are installed
   - Try `pip install psycopg2-binary` instead of `psycopg2`

2. **Connection refused:**
   - Check if PostgreSQL service is running: `sudo systemctl status postgresql`
   - Verify PostgreSQL is listening on the correct port: `sudo netstat -tlnp | grep 5432`

3. **Authentication failed:**
   - Check PostgreSQL user permissions
   - Verify password in DATABASE_URL

4. **Database doesn't exist:**
   - Create database manually as shown in setup steps
   - Ensure user has CREATE privileges

### Environment Variables

Required environment variables for PostgreSQL:

```bash
DATABASE_URL=postgres://user:password@host:port/database
DJANGO_SECRET_KEY=your-secret-key
DJANGO_DEBUG=False
DJANGO_ALLOWED_HOSTS=localhost,your-domain.com
```

### Performance Optimization

For production PostgreSQL:

1. **Connection pooling** (already configured in settings_prod.py)
2. **Query optimization** with database indexes
3. **Connection persistence** with CONN_MAX_AGE
4. **Read replicas** for high-traffic applications

## Monitoring

Check database performance:

```bash
# Django database queries logging
python manage.py shell
>>> from django.db import connection
>>> print(connection.queries)

# PostgreSQL monitoring
sudo -u postgres psql
\l+  -- List databases with sizes
SELECT * FROM pg_stat_activity;  -- Active connections
```