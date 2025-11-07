import React, { useState } from 'react';
import { useSettings } from '../hooks/useSettings';
import { api } from '../api/client';

interface SettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export default function SettingsModal({ isOpen, onClose }: SettingsModalProps) {
  const { settings, updateSetting } = useSettings();
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [statusMessage, setStatusMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);
  const [loading, setLoading] = useState<'export' | 'delete' | null>(null);

  if (!isOpen) return null;

  const handleOverlayClick = (e: React.MouseEvent) => {
    if (e.target === e.currentTarget) {
      onClose();
    }
  };

  const handleExportData = async () => {
    try {
      setLoading('export');
      setStatusMessage(null);
      const response = await api.requestDataExport();
      setStatusMessage({ type: 'success', text: response.message });
    } catch (error) {
      setStatusMessage({
        type: 'error',
        text: error instanceof Error ? error.message : 'Failed to request export'
      });
    } finally {
      setLoading(null);
    }
  };

  const handleDeleteAccount = async () => {
    try {
      setLoading('delete');
      setStatusMessage(null);
      const response = await api.requestAccountDeletion();
      setStatusMessage({ type: 'success', text: response.message });
      setShowDeleteConfirm(false);
    } catch (error) {
      setStatusMessage({
        type: 'error',
        text: error instanceof Error ? error.message : 'Failed to request account deletion'
      });
    } finally {
      setLoading(null);
    }
  };

  return (
    <div
      className="fixed inset-0 bg-black bg-opacity-50 z-50 flex items-center justify-center p-4"
      onClick={handleOverlayClick}
    >
      <div className="bg-neutral-800 rounded-2xl shadow-2xl max-w-2xl w-full max-h-[90vh] overflow-y-auto">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-neutral-700">
          <h2 className="text-2xl font-semibold text-white">Settings</h2>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-white transition-colors p-2 rounded-lg hover:bg-neutral-700"
            aria-label="Close settings"
          >
            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M6 18L18 6M6 6l12 12"
              />
            </svg>
          </button>
        </div>

        {/* Settings Content */}
        <div className="p-6 space-y-6">
          {/* Download Features Section */}
          <section>
            <h3 className="text-lg font-semibold text-white mb-4">Download Features</h3>
            <div className="space-y-4">
              {/* Enable Download Buttons Toggle */}
              <div className="flex items-start justify-between p-4 bg-neutral-750 rounded-xl">
                <div className="flex-1">
                  <label
                    htmlFor="enable-download-buttons"
                    className="text-white font-medium cursor-pointer"
                  >
                    Enable Download Buttons
                  </label>
                  <p className="text-sm text-gray-400 mt-1">
                    Show a download button on each video card that copies a yt-dlp command to your
                    clipboard. The command includes metadata, thumbnail, and subtitle downloads.
                  </p>
                </div>
                <div className="ml-4">
                  <button
                    id="enable-download-buttons"
                    role="switch"
                    aria-checked={settings.enableDownloadButtons}
                    onClick={() =>
                      updateSetting('enableDownloadButtons', !settings.enableDownloadButtons)
                    }
                    className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 focus:ring-offset-neutral-800 ${
                      settings.enableDownloadButtons ? 'bg-blue-600' : 'bg-neutral-600'
                    }`}
                  >
                    <span
                      className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                        settings.enableDownloadButtons ? 'translate-x-6' : 'translate-x-1'
                      }`}
                    />
                  </button>
                </div>
              </div>
            </div>
          </section>

          {/* Status Message */}
          {statusMessage && (
            <div
              className={`p-4 rounded-xl ${
                statusMessage.type === 'success'
                  ? 'bg-green-900/30 border border-green-700'
                  : 'bg-red-900/30 border border-red-700'
              }`}
            >
              <p
                className={`text-sm ${
                  statusMessage.type === 'success' ? 'text-green-300' : 'text-red-300'
                }`}
              >
                {statusMessage.text}
              </p>
            </div>
          )}

          {/* Account Settings Section */}
          <section>
            <h3 className="text-lg font-semibold text-white mb-4">Account Settings</h3>
            <div className="space-y-3">
              {/* Export Data */}
              <button
                onClick={handleExportData}
                disabled={loading !== null}
                aria-disabled={loading !== null}
                aria-busy={loading === 'export'}
                className="w-full flex items-center justify-between p-4 bg-neutral-750 rounded-xl hover:bg-neutral-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <div className="flex items-center gap-3">
                  <svg
                    className="w-5 h-5 text-blue-400"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"
                    />
                  </svg>
                  <div className="text-left">
                    <div className="text-white font-medium">Export Data</div>
                    <div className="text-xs text-gray-400">
                      Download your watched history and preferences
                    </div>
                  </div>
                </div>
                {loading === 'export' ? (
                  <div className="w-5 h-5 border-2 border-blue-400 border-t-transparent rounded-full animate-spin" />
                ) : (
                  <svg
                    className="w-5 h-5 text-gray-400"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M9 5l7 7-7 7"
                    />
                  </svg>
                )}
              </button>

              {/* Delete Account */}
              <button
                onClick={() => setShowDeleteConfirm(true)}
                disabled={loading !== null}
                aria-disabled={loading !== null}
                className="w-full flex items-center justify-between p-4 bg-neutral-750 rounded-xl hover:bg-red-900/20 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <div className="flex items-center gap-3">
                  <svg
                    className="w-5 h-5 text-red-400"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"
                    />
                  </svg>
                  <div className="text-left">
                    <div className="text-white font-medium">Delete Account</div>
                    <div className="text-xs text-gray-400">
                      Permanently delete your account and all data
                    </div>
                  </div>
                </div>
                <svg
                  className="w-5 h-5 text-gray-400"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M9 5l7 7-7 7"
                  />
                </svg>
              </button>
            </div>
          </section>
        </div>

        {/* Footer */}
        <div className="p-6 border-t border-neutral-700 flex justify-end">
          <button
            onClick={onClose}
            className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors font-medium"
          >
            Done
          </button>
        </div>
      </div>

      {/* Delete Confirmation Modal */}
      {showDeleteConfirm && (
        <div className="fixed inset-0 bg-black bg-opacity-70 z-[60] flex items-center justify-center p-4">
          <div className="bg-neutral-800 rounded-2xl shadow-2xl max-w-md w-full border-2 border-red-900/50">
            <div className="p-6">
              <div className="flex items-center gap-3 mb-4">
                <div className="w-12 h-12 rounded-full bg-red-900/30 flex items-center justify-center">
                  <svg
                    className="w-6 h-6 text-red-400"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
                    />
                  </svg>
                </div>
                <div>
                  <h3 className="text-xl font-semibold text-white">Delete Account?</h3>
                  <p className="text-sm text-gray-400">This action cannot be undone</p>
                </div>
              </div>

              <div className="space-y-3 mb-6">
                <p className="text-gray-300">
                  You will receive a confirmation email with a link to complete the deletion.
                </p>
                <div className="bg-red-900/20 border border-red-800 rounded-lg p-3">
                  <p className="text-sm text-red-300">
                    This will permanently delete:
                  </p>
                  <ul className="text-sm text-red-300 list-disc list-inside mt-2 space-y-1">
                    <li>Your account and profile</li>
                    <li>All subscription data</li>
                    <li>All watched video history</li>
                  </ul>
                </div>
              </div>

              <div className="flex gap-3">
                <button
                  onClick={() => setShowDeleteConfirm(false)}
                  disabled={loading === 'delete'}
                  aria-disabled={loading === 'delete'}
                  className="flex-1 px-4 py-2 bg-neutral-700 hover:bg-neutral-600 text-white rounded-lg transition-colors font-medium disabled:opacity-50"
                >
                  Cancel
                </button>
                <button
                  onClick={handleDeleteAccount}
                  disabled={loading === 'delete'}
                  aria-disabled={loading === 'delete'}
                  aria-busy={loading === 'delete'}
                  className="flex-1 px-4 py-2 bg-red-600 hover:bg-red-700 text-white rounded-lg transition-colors font-medium disabled:opacity-50 flex items-center justify-center gap-2"
                >
                  {loading === 'delete' ? (
                    <>
                      <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                      Sending...
                    </>
                  ) : (
                    'Send Confirmation Email'
                  )}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
