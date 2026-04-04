import React, { useState } from 'react';
import { Shield, Lock, AlertTriangle, LogOut, ChevronRight, CheckCircle2 } from 'lucide-react';
import { api } from '../lib/api';

const PasswordResetModal = ({ isOpen, user, onResetSuccess, onLogout }) => {
    const [oldPassword, setOldPassword] = useState('');
    const [newPassword, setNewPassword] = useState('');
    const [confirmPassword, setConfirmPassword] = useState('');
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);
    const [success, setSuccess] = useState(false);

    if (!isOpen) return null;

    const handleSubmit = async (e) => {
        e.preventDefault();
        setError(null);
        
        // Basic Client Side Validation
        if (!oldPassword || !newPassword || !confirmPassword) {
            setError('All fields are required.');
            return;
        }
        if (newPassword !== confirmPassword) {
            setError('New passwords do not match.');
            return;
        }
        if (newPassword.length < 8) {
            setError('New password must be at least 8 characters.');
            return;
        }

        setLoading(true);
        try {
            await api.changePassword(oldPassword, newPassword);
            setSuccess(true);
            setTimeout(() => {
                onResetSuccess();
            }, 1500);
        } catch (err) {
            setError(err.message || 'Failed to update password. Please check your current password.');
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="fixed inset-0 z-[9999] flex items-center justify-center bg-black/80 backdrop-blur-md">
            <div className="w-full max-w-md border border-white/10 bg-[#0a0a0b] p-8 shadow-2xl shadow-blue-500/10">
                <div className="mb-6 flex items-center gap-3">
                    <div className="flex h-12 w-12 items-center justify-center rounded-lg bg-blue-500/10 text-blue-400">
                        <Shield size={28} />
                    </div>
                    <div>
                        <h2 className="text-xl font-bold tracking-tight text-white">Security Update Required</h2>
                        <p className="text-xs font-medium uppercase tracking-wider text-white/40">Credential Governance / IAM-05</p>
                    </div>
                </div>

                {success ? (
                    <div className="flex flex-col items-center justify-center py-8 text-center">
                        <div className="mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-green-500/10 text-green-400">
                            <CheckCircle2 size={40} />
                        </div>
                        <h3 className="text-lg font-bold text-white">Identity Hardened</h3>
                        <p className="mt-2 text-sm text-white/60">Your credentials have been rotated. Returning to dashboard...</p>
                    </div>
                ) : (
                    <>
                        <div className="mb-6 rounded-lg border border-yellow-500/20 bg-yellow-500/5 p-4">
                            <div className="flex gap-3">
                                <AlertTriangle className="shrink-0 text-yellow-500" size={18} />
                                <p className="text-sm text-yellow-200/80">
                                    An administrator has initiated a mandatory password reset for your account <span className="font-bold text-white">@{user?.username}</span>. Access to technical operations is restricted until reset.
                                </p>
                            </div>
                        </div>

                        <form onSubmit={handleSubmit} className="space-y-4">
                            <div>
                                <label className="mb-1 block text-xs font-bold uppercase tracking-widest text-white/40">Current Password</label>
                                <div className="relative">
                                    <Lock className="absolute left-3 top-1/2 -translate-y-1/2 text-white/20" size={16} />
                                    <input
                                        type="password"
                                        value={oldPassword}
                                        onChange={(e) => setOldPassword(e.target.value)}
                                        className="w-full border border-white/10 bg-white/5 py-3 pl-10 pr-4 text-white outline-none focus:border-blue-500/50 focus:bg-white/10"
                                        placeholder="••••••••"
                                        required
                                    />
                                </div>
                            </div>

                            <div className="grid grid-cols-1 gap-4">
                                <div>
                                    <label className="mb-1 block text-xs font-bold uppercase tracking-widest text-white/40">New Password</label>
                                    <input
                                        type="password"
                                        value={newPassword}
                                        onChange={(e) => setNewPassword(e.target.value)}
                                        className="w-full border border-white/10 bg-white/5 py-3 px-4 text-white outline-none focus:border-blue-500/50 focus:bg-white/10"
                                        placeholder="Minimum 8 characters"
                                        required
                                    />
                                </div>
                                <div>
                                    <label className="mb-1 block text-xs font-bold uppercase tracking-widest text-white/40">Confirm New Password</label>
                                    <input
                                        type="password"
                                        value={confirmPassword}
                                        onChange={(e) => setConfirmPassword(e.target.value)}
                                        className="w-full border border-white/10 bg-white/5 py-3 px-4 text-white outline-none focus:border-blue-500/50 focus:bg-white/10"
                                        placeholder="Repeat new password"
                                        required
                                    />
                                </div>
                            </div>

                            {error && (
                                <div className="rounded border border-red-500/20 bg-red-500/5 p-3 text-xs text-red-400">
                                    {error}
                                </div>
                            )}

                            <button
                                type="submit"
                                disabled={loading}
                                className="flex w-full items-center justify-center gap-2 bg-blue-600 py-4 font-bold text-white transition-all hover:bg-blue-500 disabled:opacity-50"
                            >
                                {loading ? 'Processing Identity Update...' : (
                                    <>
                                        Update Credentials
                                        <ChevronRight size={18} />
                                    </>
                                )}
                            </button>
                        </form>

                        <div className="mt-8 border-t border-white/5 pt-6">
                            <button
                                onClick={onLogout}
                                className="flex items-center gap-2 text-xs font-bold uppercase tracking-widest text-white/30 transition-colors hover:text-white"
                            >
                                <LogOut size={16} />
                                Terminate Session
                            </button>
                        </div>
                    </>
                )}
            </div>
        </div>
    );
};

export default PasswordResetModal;
