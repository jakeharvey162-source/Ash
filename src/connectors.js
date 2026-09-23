export const CONNECTOR_CATALOG = [
  {
    key: 'android_share',
    name: 'Android Share',
    category: 'device',
    description: 'Share Ash output to apps installed on the phone.',
    permissions: ['share'],
    native: true,
    builtIn: true
  },
  {
    key: 'android_notifications',
    name: 'Notifications',
    category: 'device',
    description: 'Let Ash surface automation results and reminders on Android.',
    permissions: ['notifications'],
    native: true,
    builtIn: true
  },
  {
    key: 'android_clipboard',
    name: 'Clipboard',
    category: 'device',
    description: 'Copy verified Ash output for use in other apps.',
    permissions: ['clipboard'],
    native: true,
    builtIn: true
  },
  {
    key: 'android_browser',
    name: 'Browser',
    category: 'device',
    description: 'Open approved links and destinations from Ash.',
    permissions: ['open_url'],
    native: true,
    builtIn: true
  },
  {
    key: 'gmail',
    name: 'Gmail',
    category: 'cloud',
    description: 'Read mail and draft or send messages after user authorization.',
    permissions: ['mail.read','mail.draft','mail.send'],
    native: false,
    builtIn: false
  },
  {
    key: 'google_calendar',
    name: 'Google Calendar',
    category: 'cloud',
    description: 'Read availability and create or update calendar events with approval.',
    permissions: ['calendar.read','calendar.write'],
    native: false,
    builtIn: false
  },
  {
    key: 'google_drive',
    name: 'Google Drive',
    category: 'cloud',
    description: 'Read and work with selected files the user authorizes.',
    permissions: ['drive.read','drive.write_selected'],
    native: false,
    builtIn: false
  },
  {
    key: 'github',
    name: 'GitHub',
    category: 'developer',
    description: 'Work with repositories, issues, branches and pull requests.',
    permissions: ['repo.read','repo.write_selected'],
    native: false,
    builtIn: false
  }
];

export function catalogByKey(key) {
  return CONNECTOR_CATALOG.find(x => x.key === key) || null;
}

export function normalizeIntegration(row) {
  return {
    key: row.integration_key,
    name: row.display_name,
    status: row.status,
    config: row.config || {}
  };
}
