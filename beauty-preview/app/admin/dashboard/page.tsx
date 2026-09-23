'use client';

/**
 * app/admin/dashboard/page.tsx — داشبورد جامع مدیریت و CRM نوبت‌ها
 * شامل: آمار، مدیریت مراجعین، گالری رفرنس‌ها، تصویر هیرو و تاریخچه چت‌های کاربران (Chat Logs)
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';

import {
  AdminAuthError,
  adminFetch,
  clearAdminToken,
  faNumber,
  faTime,
  getAdminToken,
} from '@/admin-client';
import {
  HERO_IMAGE_URL,
} from '@/options';
import { SERVICE_TECHNIQUES, type TechniqueStyleOption } from '@/techniques';
import { getPlanConfig } from '@/plan-config';
import { TenantSettings } from '@/db';

interface StatEvent {
  type: 'visit' | 'preview';
  time: string;
  style?: string;
}

interface StatsResponse {
  ok: boolean;
  visits: number;
  previews: number;
  todayVisits: number;
  todayPreviews: number;
  history: StatEvent[];
}

interface LeadRecord {
  id: string;
  fullName: string;
  phoneNumber: string;
  instagramId?: string | null;
  selectedService: string;
  selectedStyle: string;
  originalImageUrl?: string | null;
  resultImageUrl?: string | null;
  status: 'new' | 'contacted' | 'booked' | 'cancelled';
  notes?: string | null;
  createdAt: string;
  updatedAt: string;
}

interface ChatLogRecord {
  id: string;
  sessionId: string;
  userMessage: string;
  aiResponse: string;
  createdAt: string;
}

type TabKey = 'stats' | 'leads' | 'references' | 'hero' | 'assistant';
type Banner = { kind: 'ok' | 'error'; text: string } | null;

const TABS: { key: TabKey; icon: string; label: string }[] = [
  { key: 'stats', icon: '📊', label: 'آمار بازدید' },
  { key: 'leads', icon: '👥', label: 'مدیریت مراجعین (CRM)' },
  { key: 'references', icon: '🖼️', label: 'گالری رفرنس‌ها' },
  { key: 'hero', icon: '🌟', label: 'تصویر هیرو' },
  { key: 'assistant', icon: '🤖', label: 'دستیار هوشمند و لاگ چت‌ها' },
];

const ACCEPT_IMAGE = 'image/png,image/jpeg,image/webp';

export default function AdminDashboardPage() {
  const router = useRouter();

  const [ready, setReady] = useState(false);
  const [tab, setTab] = useState<TabKey>('stats');
  const [banner, setBanner] = useState<Banner>(null);

  /* آمار */
  const [stats, setStats] = useState<StatsResponse | null>(null);

  /* مراجعین CRM */
  const [leads, setLeads] = useState<LeadRecord[]>([]);
  const [selectedLead, setSelectedLead] = useState<LeadRecord | null>(null);
  const [leadNotesInput, setLeadNotesInput] = useState('');

  /* تب گالری رفرنس‌ها */
  const [referenceService, setReferenceService] = useState<'brows' | 'lips' | 'eyeliner'>('brows');
  const [uploadingKey, setUploadingKey] = useState<string | null>(null);
  const [version, setVersion] = useState(0);

  /* تصویر هیرو */
  const [heroActive, setHeroActive] = useState(false);
  const [heroUploading, setHeroUploading] = useState(false);
  const heroInput = useRef<HTMLInputElement | null>(null);

  /* اطلاعات پلن و سالن */
  const [tenant, setTenant] = useState<TenantSettings>({
    id: 'default',
    name: 'استودیو تخصصی عسل رجبی',
    planTier: 'gold',
    customAssistantName: 'غزل - مشاور اختصاصی استودیو عسل رجبی',
    monthlyGenerationsLimit: -1,
    currentMonthUsage: 14,
    updatedAt: '',
  });
  const [upgradeModalOpen, setUpgradeModalOpen] = useState(false);

  /* دستیار هوشمند و لاگ چت‌ها */
  const [assistantEnabled, setAssistantEnabled] = useState(true);
  const [welcomeMessage, setWelcomeMessage] = useState(
    'سلام عزیزم ✨ من غزل هستم، مشاور هوشمند مرکز عسل رجبی.',
  );
  const [chatLogs, setChatLogs] = useState<ChatLogRecord[]>([]);
  const [chatLogsLoading, setChatLogsLoading] = useState(false);

  const fileInputs = useRef<Record<string, HTMLInputElement | null>>({});

  const loadTenant = useCallback(async () => {
    try {
      const res = await adminFetch('/api/admin/tenant');
      const data = await res.json();
      if (res.ok && data.ok && data.tenant) {
        setTenant(data.tenant);
        if (data.tenant.customAssistantName) {
          setWelcomeMessage(`سلام عزیزم ✨ من ${data.tenant.customAssistantName} هستم، مشاور هوشمند سالن.`);
        }
      }
    } catch {
      // نادیده گرفتن
    }
  }, []);

  useEffect(() => {
    if (!getAdminToken()) {
      router.replace('/admin');
      return;
    }
    setReady(true);
  }, [router]);

  const handleLogout = useCallback(() => {
    clearAdminToken();
    router.replace('/admin');
  }, [router]);

  const handleAuthError = useCallback(
    (error: unknown): boolean => {
      if (error instanceof AdminAuthError) {
        setBanner({ kind: 'error', text: error.message });
        setTimeout(() => router.replace('/admin'), 1200);
        return true;
      }
      return false;
    },
    [router],
  );

  const loadStats = useCallback(async () => {
    try {
      const res = await adminFetch('/api/admin/stats?limit=15');
      const data = (await res.json()) as StatsResponse;
      if (res.ok && data.ok) setStats(data);
    } catch (error) {
      if (handleAuthError(error)) return;
    }
  }, [handleAuthError]);

  const loadLeads = useCallback(async () => {
    try {
      const res = await adminFetch('/api/admin/leads');
      const data = await res.json();
      if (res.ok && data.ok) {
        setLeads(data.leads || []);
      }
    } catch (error) {
      if (handleAuthError(error)) return;
    }
  }, [handleAuthError]);

  const loadChatLogs = useCallback(async () => {
    setChatLogsLoading(true);
    try {
      const res = await adminFetch('/api/admin/chat-logs');
      const data = await res.json();
      if (res.ok && data.ok) {
        setChatLogs(data.logs || []);
      }
    } catch (error) {
      if (handleAuthError(error)) return;
    } finally {
      setChatLogsLoading(false);
    }
  }, [handleAuthError]);

  useEffect(() => {
    if (!ready) return;
    void loadStats();
    void loadLeads();
    void loadChatLogs();
    void loadTenant();
  }, [ready, loadStats, loadLeads, loadChatLogs, loadTenant]);

  /* آپلود رفرنس برای هر خدمت */
  const handleReferenceUpload = async (service: 'brows' | 'lips' | 'eyeliner', styleKey: string, file?: File | null) => {
    if (!file) return;
    setUploadingKey(styleKey);
    setBanner(null);

    try {
      const form = new FormData();
      form.append('service', service);
      form.append('styleKey', styleKey);
      form.append('file', file);

      const res = await adminFetch('/api/admin/upload-reference', {
        method: 'POST',
        body: form,
      });
      const data = await res.json();

      if (!res.ok || !data.ok) {
        setBanner({ kind: 'error', text: data.error || 'آپلود رفرنس ناموفق بود.' });
        return;
      }

      setVersion((v) => v + 1);
      setBanner({ kind: 'ok', text: `تصویر رفرنس مدل ${styleKey} با موفقیت ذخیره شد ✓` });
    } catch (error) {
      if (handleAuthError(error)) return;
      setBanner({ kind: 'error', text: 'ارتباط با سرور برقرار نشد.' });
    } finally {
      setUploadingKey(null);
      const input = fileInputs.current[`${service}_${styleKey}`];
      if (input) input.value = '';
    }
  };

  /* آپلود هیرو */
  const handleHeroUpload = async (file?: File | null) => {
    if (!file) return;
    setHeroUploading(true);
    setBanner(null);
    try {
      const form = new FormData();
      form.append('file', file);

      const res = await adminFetch('/api/admin/upload-hero', { method: 'POST', body: form });
      const data = await res.json();

      if (!res.ok || !data.ok) {
        setBanner({ kind: 'error', text: data.error || 'آپلود هیرو ناموفق بود.' });
        return;
      }
      setHeroActive(true);
      setVersion((v) => v + 1);
      setBanner({ kind: 'ok', text: 'تصویر هیرو با موفقیت ذخیره شد ✓' });
    } catch (error) {
      if (handleAuthError(error)) return;
    } finally {
      setHeroUploading(false);
      if (heroInput.current) heroInput.current.value = '';
    }
  };

  /* به‌روزرسانی وضعیت لید */
  const handleUpdateLeadStatus = async (id: string, status: LeadRecord['status'], notes?: string) => {
    try {
      const res = await adminFetch(`/api/admin/leads/${id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status, notes }),
      });
      const data = await res.json();
      if (res.ok && data.ok) {
        setBanner({ kind: 'ok', text: 'وضعیت پرونده به‌روزرسانی شد ✓' });
        void loadLeads();
        if (selectedLead?.id === id) {
          setSelectedLead(data.lead);
        }
      }
    } catch {
      setBanner({ kind: 'error', text: 'خطا در ویرایش وضعیت' });
    }
  };

  /* حذف لید */
  const handleDeleteLead = async (id: string) => {
    if (!confirm('آیا از حذف کامل این پرونده مطمئن هستید؟')) return;
    try {
      const res = await adminFetch(`/api/admin/leads/${id}`, { method: 'DELETE' });
      const data = await res.json();
      if (res.ok && data.ok) {
        setBanner({ kind: 'ok', text: 'پرونده با موفقیت حذف گردید.' });
        setSelectedLead(null);
        void loadLeads();
      }
    } catch {
      setBanner({ kind: 'error', text: 'خطا در حذف پرونده' });
    }
  };

  if (!ready) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-neutral-950">
        <span className="h-8 w-8 animate-spin rounded-full border-2 border-amber-500/30 border-t-amber-400" />
      </main>
    );
  }

  const activeTechniqueList: TechniqueStyleOption[] =
    referenceService === 'brows'
      ? SERVICE_TECHNIQUES.eyebrows
      : referenceService === 'lips'
      ? SERVICE_TECHNIQUES.lips
      : SERVICE_TECHNIQUES.eyeliner;

  return (
    <div className="flex min-h-screen flex-col md:flex-row bg-neutral-950 text-neutral-100 font-[family-name:var(--font-vazirmatn)]">
      {/* سایدبار */}
      <aside className="flex w-full shrink-0 flex-col border-e border-neutral-800 bg-neutral-900/60 p-5 md:min-h-screen md:w-64">
        <div className="mb-6 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-full bg-amber-500 text-neutral-950 font-black flex items-center justify-center text-xs">
              AR
            </div>
            <div>
              <h1 className="text-sm font-bold text-neutral-100">{tenant.name}</h1>
              <p className="text-[10px] text-emerald-400">پنل مدیریت سالن‌دار</p>
            </div>
          </div>
        </div>

        {/* کارت نمایش وضعیت اشتراک و پلن سالن */}
        <div className="mb-6 p-3.5 rounded-xl bg-neutral-950 border border-amber-500/30 text-xs">
          <div className="flex items-center justify-between mb-2">
            <span className="text-neutral-400 text-[11px]">پلن فعال:</span>
            <span className={`px-2 py-0.5 rounded-full font-bold text-[10px] ${
              tenant.planTier === 'gold'
                ? 'bg-amber-500/20 text-amber-300 border border-amber-500/40'
                : tenant.planTier === 'silver'
                ? 'bg-neutral-800 text-neutral-200 border border-neutral-700'
                : 'bg-amber-900/30 text-amber-500 border border-amber-800'
            }`}>
              {getPlanConfig(tenant.planTier).badge}
            </span>
          </div>
          <div className="flex items-center justify-between text-[11px] text-neutral-400 mb-3">
            <span>مصرف این ماه:</span>
            <span className="font-mono text-neutral-200">
              {tenant.currentMonthUsage} / {tenant.monthlyGenerationsLimit === -1 ? 'نامحدود' : tenant.monthlyGenerationsLimit}
            </span>
          </div>
          <button
            onClick={() => setUpgradeModalOpen(true)}
            className="w-full py-1.5 rounded-lg bg-gradient-to-r from-amber-500 to-amber-600 hover:from-amber-400 text-neutral-950 font-bold text-[11px] cursor-pointer shadow-md shadow-amber-500/10"
          >
            ⭐ ارتقای اشتراک
          </button>
        </div>

        <nav className="flex-1 space-y-1.5">
          {TABS.map((t) => (
            <button
              key={t.key}
              onClick={() => {
                setTab(t.key);
                setBanner(null);
                if (t.key === 'leads') void loadLeads();
                if (t.key === 'assistant') void loadChatLogs();
              }}
              className={`w-full flex items-center gap-2.5 px-3.5 py-2.5 rounded-xl text-xs font-semibold transition-all cursor-pointer ${
                tab === t.key
                  ? 'bg-amber-500/20 text-amber-300 border border-amber-500/40'
                  : 'text-neutral-400 hover:text-neutral-200 hover:bg-neutral-800/40'
              }`}
            >
              <span>{t.icon}</span>
              <span>{t.label}</span>
              {t.key === 'leads' && leads.length > 0 && (
                <span className="ms-auto bg-emerald-500/20 text-emerald-300 px-2 py-0.5 rounded-full text-[10px]">
                  {leads.length}
                </span>
              )}
            </button>
          ))}
        </nav>

        <div className="pt-4 border-t border-neutral-800">
          <button
            onClick={handleLogout}
            className="w-full px-3 py-2 rounded-xl text-xs text-red-400 hover:bg-red-500/10 transition-colors text-right cursor-pointer"
          >
            ← خروج از حساب
          </button>
        </div>
      </aside>

      {/* محتوا */}
      <main className="flex-1 p-6 md:p-8 overflow-y-auto">
        {banner && (
          <div
            className={`mb-6 p-4 rounded-xl text-xs ${
              banner.kind === 'ok'
                ? 'bg-emerald-950/60 border border-emerald-700 text-emerald-300'
                : 'bg-red-950/60 border border-red-700 text-red-300'
            }`}
          >
            {banner.text}
          </div>
        )}

        {/* ۱. آمار */}
        {tab === 'stats' && (
          <div className="space-y-6">
            <h2 className="text-lg font-bold text-neutral-100 mb-4">آمار عملکرد پلتفرم</h2>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
              <StatCard title="کل بازدیدها" value={stats?.visits ?? 0} icon="👁️" />
              <StatCard title="پیش‌نمایش‌ها" value={stats?.previews ?? 0} icon="🎨" />
              <StatCard title="بازدید امروز" value={stats?.todayVisits ?? 0} icon="📈" />
              <StatCard title="کل پرونده‌های CRM" value={leads.length} icon="👥" />
            </div>
          </div>
        )}

        {/* ۲. مدیریت مراجعین (CRM) */}
        {tab === 'leads' && (
          <div className="space-y-6">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-lg font-bold text-neutral-100">مدیریت مراجعین و نوبت‌ها (CRM)</h2>
                <p className="text-xs text-neutral-400 mt-0.5">پایگاه داده سبک SQLite و مدیریت فایل‌ها در دیسک</p>
              </div>
              <button
                onClick={() => void loadLeads()}
                className="px-3.5 py-1.5 rounded-xl border border-neutral-700 text-xs text-neutral-300 hover:bg-neutral-800 cursor-pointer"
              >
                🔄 تازه‌سازی
              </button>
            </div>

            {leads.length === 0 ? (
              <div className="p-8 rounded-2xl bg-neutral-900/40 border border-neutral-800 text-center text-xs text-neutral-400">
                هنوز درخواستی ثبت نشده است.
              </div>
            ) : (
              <div className="overflow-x-auto rounded-2xl border border-neutral-800 bg-neutral-900/60">
                <table className="w-full text-xs text-right">
                  <thead className="bg-neutral-950/80 text-neutral-400 border-b border-neutral-800">
                    <tr>
                      <th className="p-3.5">نام مراجع</th>
                      <th className="p-3.5">شماره تماس</th>
                      <th className="p-3.5">خدمت</th>
                      <th className="p-3.5">وضعیت</th>
                      <th className="p-3.5">تاریخ ثبت</th>
                      <th className="p-3.5">عملیات</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-neutral-800/60">
                    {leads.map((lead) => (
                      <tr key={lead.id} className="hover:bg-neutral-800/30 transition-colors">
                        <td className="p-3.5 font-bold text-neutral-100">{lead.fullName}</td>
                        <td className="p-3.5 font-mono text-amber-400" dir="ltr">
                          {lead.phoneNumber}
                        </td>
                        <td className="p-3.5 text-neutral-300">{lead.selectedStyle}</td>
                        <td className="p-3.5">
                          <select
                            value={lead.status}
                            onChange={(e) =>
                              handleUpdateLeadStatus(
                                lead.id,
                                e.target.value as LeadRecord['status'],
                                lead.notes ?? undefined,
                              )
                            }
                            className="bg-neutral-950 border border-neutral-800 rounded-lg px-2 py-1 text-[11px] text-neutral-200 cursor-pointer"
                          >
                            <option value="new">جدید (New)</option>
                            <option value="contacted">تماس گرفته شد</option>
                            <option value="booked">رزرو قطعی شد</option>
                            <option value="cancelled">لغو شده</option>
                          </select>
                        </td>
                        <td className="p-3.5 font-mono text-neutral-500 text-[11px]">
                          {faTime(lead.createdAt)}
                        </td>
                        <td className="p-3.5 flex items-center gap-2">
                          <button
                            onClick={() => {
                              setSelectedLead(lead);
                              setLeadNotesInput(lead.notes || '');
                            }}
                            className="px-2.5 py-1 rounded-lg bg-amber-500/20 text-amber-300 hover:bg-amber-500/30 text-[11px] cursor-pointer"
                          >
                            مشاهده جزئیات
                          </button>
                          <a
                            href={`https://wa.me/${lead.phoneNumber.replace(/^0/, '98')}?text=${encodeURIComponent(
                              `سلام ${lead.fullName} عزیز، از استودیو عسل رجبی در خدمت شما هستیم.`,
                            )}`}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="px-2.5 py-1 rounded-lg bg-emerald-950 text-emerald-300 border border-emerald-800 hover:bg-emerald-900 text-[11px]"
                          >
                            واتساپ
                          </a>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            {/* مودال جزئیات پرونده */}
            {selectedLead && (
              <div className="fixed inset-0 z-50 bg-neutral-950/80 backdrop-blur-md flex items-center justify-center p-4">
                <div className="bg-neutral-900 border border-neutral-800 rounded-2xl max-w-lg w-full p-6 max-h-[90vh] overflow-y-auto">
                  <div className="flex justify-between items-center mb-4 pb-2 border-b border-neutral-800">
                    <h3 className="text-base font-bold text-neutral-100">
                      پرونده: {selectedLead.fullName}
                    </h3>
                    <button
                      onClick={() => setSelectedLead(null)}
                      className="text-neutral-400 hover:text-neutral-100 text-sm cursor-pointer"
                    >
                      ✕
                    </button>
                  </div>

                  <div className="space-y-3 text-xs mb-5">
                    <div className="flex justify-between p-2 rounded-lg bg-neutral-950">
                      <span className="text-neutral-400">شماره تماس:</span>
                      <a href={`tel:${selectedLead.phoneNumber}`} className="text-amber-400 font-mono font-bold" dir="ltr">
                        {selectedLead.phoneNumber}
                      </a>
                    </div>
                    {selectedLead.instagramId && (
                      <div className="flex justify-between p-2 rounded-lg bg-neutral-950">
                        <span className="text-neutral-400">اینستاگرام:</span>
                        <span className="text-neutral-200">{selectedLead.instagramId}</span>
                      </div>
                    )}
                    <div className="flex justify-between p-2 rounded-lg bg-neutral-950">
                      <span className="text-neutral-400">خدمت انتخابی:</span>
                      <span className="text-neutral-200">{selectedLead.selectedStyle}</span>
                    </div>

                    <div>
                      <label className="text-neutral-400 block mb-1">یادداشت‌های مدیر:</label>
                      <textarea
                        rows={2}
                        value={leadNotesInput}
                        onChange={(e) => setLeadNotesInput(e.target.value)}
                        placeholder="ثبت توضیحات یا هماهنگی..."
                        className="w-full p-2.5 rounded-xl bg-neutral-950 border border-neutral-800 text-xs text-neutral-100"
                      />
                      <button
                        onClick={() =>
                          handleUpdateLeadStatus(selectedLead.id, selectedLead.status, leadNotesInput)
                        }
                        className="mt-1 px-3 py-1 bg-amber-500 text-neutral-950 font-bold rounded-lg text-[11px] cursor-pointer"
                      >
                        ذخیره یادداشت
                      </button>
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-3 mb-6">
                    {selectedLead.originalImageUrl && (
                      <div>
                        <p className="text-[11px] text-neutral-400 mb-1">عکس اولیه مشتری:</p>
                        <div className="aspect-square rounded-xl overflow-hidden border border-neutral-800 bg-neutral-950 relative">
                          <img src={selectedLead.originalImageUrl} alt="عکس مشتری" className="w-full h-full object-cover" />
                        </div>
                      </div>
                    )}
                    {selectedLead.resultImageUrl && (
                      <div>
                        <p className="text-[11px] text-amber-400 mb-1">خروجی هوش مصنوعی:</p>
                        <div className="aspect-square rounded-xl overflow-hidden border border-neutral-800 bg-neutral-950 relative">
                          <img src={selectedLead.resultImageUrl} alt="خروجی AI" className="w-full h-full object-cover" />
                        </div>
                      </div>
                    )}
                  </div>

                  <div className="flex justify-between items-center pt-2 border-t border-neutral-800">
                    <button
                      onClick={() => handleDeleteLead(selectedLead.id)}
                      className="text-red-400 text-xs hover:underline cursor-pointer"
                    >
                      حذف امن پرونده
                    </button>
                    <a
                      href={`https://wa.me/${selectedLead.phoneNumber.replace(/^0/, '98')}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-neutral-950 font-bold text-xs rounded-xl"
                    >
                      گفتگو در واتساپ
                    </a>
                  </div>
                </div>
              </div>
            )}
          </div>
        )}

        {/* ۳. گالری رفرنس‌ها (ابرو، لب، خط چشم) */}
        {tab === 'references' && (
          <div className="space-y-6">
            <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-3">
              <div>
                <div className="flex items-center gap-2">
                  <h2 className="text-lg font-bold text-neutral-100">مدیریت رفرنس‌های تصویری مدل‌ها</h2>
                  {tenant.planTier !== 'gold' && (
                    <span className="px-2 py-0.5 rounded-full bg-amber-500/20 text-amber-300 border border-amber-500/40 text-[10px] font-bold">
                      🔒 آپلود اختصاصی ویژه پلن طلایی
                    </span>
                  )}
                </div>
                <p className="text-xs text-neutral-400 mt-0.5">
                  {tenant.planTier === 'gold'
                    ? 'آپلود نمونه‌کارهای واقعی هر تکنیک جهت آموزش و نمایش به مشتری در ویزارد سالن شما'
                    : 'در پلن فعلی از نمونه‌کارهای استاندارد سیستم استفاده می‌شود. برای آپلود کارهای خودتان به پلن طلایی ارتقا دهید.'}
                </p>
              </div>

              {/* سوئیچ سرویس */}
              <div className="flex gap-1.5 p-1 rounded-xl bg-neutral-900 border border-neutral-800">
                {(
                  [
                    { id: 'brows', label: 'میکروبلیدینگ ابرو' },
                    { id: 'lips', label: 'شیدینگ لب' },
                    { id: 'eyeliner', label: 'خط چشم دائم' },
                  ] as const
                ).map((s) => (
                  <button
                    key={s.id}
                    onClick={() => setReferenceService(s.id)}
                    className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-all cursor-pointer ${
                      referenceService === s.id
                        ? 'bg-amber-500 text-neutral-950'
                        : 'text-neutral-400 hover:text-neutral-200'
                    }`}
                  >
                    {s.label}
                  </button>
                ))}
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {activeTechniqueList.map((technique) => {
                const inputKey = `${referenceService}_${technique.key}`;
                const isBusy = uploadingKey === technique.key;
                const imgSrc = `${technique.sampleImage}?v=${version}`;

                return (
                  <div key={technique.key} className="p-4 rounded-2xl bg-neutral-900/60 border border-neutral-800 flex flex-col justify-between">
                    <div>
                      <div className="flex items-center justify-between mb-1.5">
                        <span className="text-sm font-bold text-neutral-100">{technique.label}</span>
                        <span className="text-[10px] text-amber-400/90 font-mono">{technique.labelEn}</span>
                      </div>
                      <p className="text-xs text-neutral-400 mb-3 leading-relaxed">{technique.hint}</p>

                      <div className="relative aspect-[16/9] rounded-xl overflow-hidden border border-neutral-800 bg-neutral-950 mb-4 flex items-center justify-center">
                        <img
                          src={imgSrc}
                          alt={technique.label}
                          className="w-full h-full object-cover"
                          onError={(e) => {
                            (e.target as HTMLElement).style.display = 'none';
                          }}
                        />
                        <span className="absolute text-[11px] text-neutral-600 -z-0">تصویر پیش‌فرض سیستمی</span>
                      </div>
                    </div>

                    <div className="flex items-center justify-between pt-2 border-t border-neutral-800/80">
                      <input
                        ref={(el) => {
                          fileInputs.current[inputKey] = el;
                        }}
                        type="file"
                        accept={ACCEPT_IMAGE}
                        className="hidden"
                        onChange={(e) =>
                          void handleReferenceUpload(referenceService, technique.key, e.target.files?.[0])
                        }
                      />
                      {tenant.planTier === 'gold' ? (
                        <button
                          type="button"
                          disabled={isBusy}
                          onClick={() => fileInputs.current[inputKey]?.click()}
                          className="px-4 py-2 rounded-xl bg-amber-500 hover:bg-amber-400 text-neutral-950 font-bold text-xs transition-colors cursor-pointer disabled:opacity-50"
                        >
                          {isBusy ? 'در حال آپلود...' : 'آپلود نمونه‌کار واقعی 📸'}
                        </button>
                      ) : (
                        <button
                          type="button"
                          onClick={() => setUpgradeModalOpen(true)}
                          className="px-3 py-1.5 rounded-xl bg-neutral-800 hover:bg-neutral-700 text-amber-300 font-bold text-[11px] transition-colors cursor-pointer flex items-center gap-1"
                        >
                          <span>🔒</span>
                          <span>ارتقا به طلایی جهت آپلود</span>
                        </button>
                      )}
                      <span className="text-[10px] text-neutral-500 font-mono" dir="ltr">
                        /{referenceService}/{technique.key}.png
                      </span>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* ۴. تصویر هیرو */}
        {tab === 'hero' && (
          <div className="space-y-4">
            <h2 className="text-lg font-bold text-neutral-100 mb-2">تصویر سربرگ اصلی سایت (Hero)</h2>
            <div className="p-5 rounded-2xl bg-neutral-900/60 border border-neutral-800 max-w-lg">
              <div className="aspect-video rounded-xl overflow-hidden border border-neutral-800 bg-neutral-950 mb-4 relative">
                <img src={`${HERO_IMAGE_URL}?v=${version}`} alt="Hero" className="w-full h-full object-cover" />
              </div>
              <input
                ref={heroInput}
                type="file"
                accept={ACCEPT_IMAGE}
                className="hidden"
                onChange={(e) => void handleHeroUpload(e.target.files?.[0])}
              />
              <button
                type="button"
                disabled={heroUploading}
                onClick={() => heroInput.current?.click()}
                className="px-5 py-2.5 rounded-xl bg-amber-500 text-neutral-950 font-bold text-xs hover:bg-amber-400 cursor-pointer disabled:opacity-50"
              >
                {heroUploading ? 'در حال آپلود...' : 'تغییر عکس پرتره هیرو'}
              </button>
            </div>
          </div>
        )}

        {/* ۵. تنظیمات دستیار هوشمند و نمایش Chat Logs (اصلاح مورد ۱۶) */}
        {tab === 'assistant' && (
          <div className="space-y-8">
            <div>
              <h2 className="text-lg font-bold text-neutral-100 mb-1">تنظیمات دستیار هوشمند (غزل)</h2>
              <p className="text-xs text-neutral-400 mb-4">مدیریت پیام‌های خودکار و پیکربندی رفتار هوش مصنوعی</p>

              <div className="p-5 rounded-2xl bg-neutral-900/60 border border-neutral-800 space-y-4 max-w-xl">
                <label className="flex items-center justify-between cursor-pointer">
                  <span className="text-xs text-neutral-200">وضعیت فعال بودن چت‌بات در سایت:</span>
                  <input
                    type="checkbox"
                    disabled={tenant.planTier === 'bronze'}
                    checked={tenant.planTier !== 'bronze' && assistantEnabled}
                    onChange={(e) => setAssistantEnabled(e.target.checked)}
                    className="w-5 h-5 accent-amber-500"
                  />
                </label>

                {tenant.planTier === 'bronze' && (
                  <div className="p-3 rounded-xl bg-amber-950/40 border border-amber-500/40 text-amber-300 text-xs flex items-center justify-between">
                    <span>🔒 چت‌بات هوشمند مشاور ویژه پلن‌های نقره‌ای و طلایی است.</span>
                    <button
                      onClick={() => setUpgradeModalOpen(true)}
                      className="px-2.5 py-1 bg-amber-500 text-neutral-950 font-bold rounded-lg text-[10px]"
                    >
                      ارتقای پلن
                    </button>
                  </div>
                )}

                <div>
                  <label className="text-xs text-neutral-400 block mb-1">
                    نام و عنوان مشاور هوشمند:
                    {tenant.planTier !== 'gold' && (
                      <span className="text-[10px] text-amber-400 ms-2 font-normal">(شخصی‌سازی نام مشاور ویژه پلن طلایی)</span>
                    )}
                  </label>
                  <input
                    type="text"
                    disabled={tenant.planTier !== 'gold'}
                    value={tenant.customAssistantName || ''}
                    placeholder="مثال: سارا - مشاور تخصصی استودیو زیبایی"
                    onChange={(e) => setTenant({ ...tenant, customAssistantName: e.target.value })}
                    className="w-full p-2.5 rounded-xl bg-neutral-950 border border-neutral-800 text-xs text-neutral-100 disabled:opacity-50"
                  />
                </div>

                <div>
                  <label className="text-xs text-neutral-400 block mb-1">پیام خوشامدگویی اولیه غزل:</label>
                  <textarea
                    rows={3}
                    value={welcomeMessage}
                    onChange={(e) => setWelcomeMessage(e.target.value)}
                    className="w-full p-2.5 rounded-xl bg-neutral-950 border border-neutral-800 text-xs text-neutral-100"
                  />
                </div>

                <button
                  onClick={async () => {
                    try {
                      await adminFetch('/api/admin/tenant', {
                        method: 'PATCH',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ customAssistantName: tenant.customAssistantName }),
                      });
                      setBanner({ kind: 'ok', text: 'تنظیمات دستیار هوشمند با موفقیت ذخیره شد ✓' });
                    } catch {
                      setBanner({ kind: 'error', text: 'خطا در ذخیره تنظیمات' });
                    }
                  }}
                  className="px-4 py-2 bg-amber-500 text-neutral-950 font-bold text-xs rounded-xl cursor-pointer"
                >
                  ذخیره تنظیمات دستیار
                </button>
              </div>
            </div>

            {/* جدول تاریخچه چت‌های کاربران (Chat Logs) */}
            <div>
              <div className="flex items-center justify-between mb-3">
                <h3 className="text-sm font-bold text-neutral-100">تاریخچه پیام‌های مراجعین با غزل (Chat Logs)</h3>
                <button
                  onClick={() => void loadChatLogs()}
                  className="px-3 py-1 rounded-lg border border-neutral-800 text-[11px] text-neutral-300 hover:bg-neutral-800 cursor-pointer"
                >
                  🔄 بروزرسانی لاگ‌ها
                </button>
              </div>

              {chatLogsLoading ? (
                <p className="text-xs text-neutral-500">در حال دریافت تاریخچه چت‌ها...</p>
              ) : chatLogs.length === 0 ? (
                <div className="p-6 rounded-2xl bg-neutral-900/40 border border-neutral-800 text-center text-xs text-neutral-500">
                  هنوز مکالمه‌ای با دستیار هوشمند ثبت نشده است.
                </div>
              ) : (
                <div className="overflow-x-auto rounded-2xl border border-neutral-800 bg-neutral-900/60 max-h-96 overflow-y-auto">
                  <table className="w-full text-xs text-right">
                    <thead className="bg-neutral-950 text-neutral-400 sticky top-0 border-b border-neutral-800">
                      <tr>
                        <th className="p-3">زمان</th>
                        <th className="p-3">پیام کاربر</th>
                        <th className="p-3">پاسخ غزل (AI)</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-neutral-800/50">
                      {chatLogs.map((log) => (
                        <tr key={log.id} className="hover:bg-neutral-800/30">
                          <td className="p-3 font-mono text-[10px] text-neutral-500 whitespace-nowrap">
                            {faTime(log.createdAt)}
                          </td>
                          <td className="p-3 text-amber-300 font-medium max-w-xs">{log.userMessage}</td>
                          <td className="p-3 text-neutral-300 leading-relaxed max-w-md">{log.aiResponse}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </div>
        )}

        {/* مودال ارتقای اشتراک و انتخاب پلن تجاری */}
        {upgradeModalOpen && (
          <div className="fixed inset-0 z-50 bg-neutral-950/80 backdrop-blur-md flex items-center justify-center p-4">
            <div className="bg-neutral-900 border border-neutral-800 rounded-2xl max-w-2xl w-full p-6 max-h-[90vh] overflow-y-auto">
              <div className="flex justify-between items-center mb-4 pb-2 border-b border-neutral-800">
                <h3 className="text-base font-bold text-neutral-100">
                  ارتقای پلن اشتراک پلتفرم هوش مصنوعی
                </h3>
                <button
                  onClick={() => setUpgradeModalOpen(false)}
                  className="text-neutral-400 hover:text-neutral-100 text-sm cursor-pointer"
                >
                  ✕
                </button>
              </div>

              <p className="text-xs text-neutral-400 mb-6">
                پلن مورد نظرتان را انتخاب کنید تا امکانات پیشرفته متناسب با نیاز سالن شما فعال شود:
              </p>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
                {/* پلن برنزی */}
                <div className={`p-4 rounded-xl border flex flex-col justify-between ${
                  tenant.planTier === 'bronze' ? 'bg-amber-500/10 border-amber-400' : 'bg-neutral-950 border-neutral-800'
                }`}>
                  <div>
                    <h4 className="text-sm font-bold text-neutral-100 mb-1">🥉 پلن برنزی</h4>
                    <p className="text-[11px] text-amber-400 font-bold mb-3">۵۰۰,۰۰۰ تومان / ماه</p>
                    <ul className="text-[10px] text-neutral-400 space-y-1.5 list-disc list-inside">
                      <li>فقط پیش‌نمایش ابرو</li>
                      <li>۵۰ پیش‌نمایش در ماه</li>
                      <li>واترمارک روی تصویر</li>
                      <li>CRM ثبت نوبت‌ها</li>
                    </ul>
                  </div>
                  <button
                    disabled={tenant.planTier === 'bronze'}
                    onClick={async () => {
                      await adminFetch('/api/admin/tenant', {
                        method: 'PATCH',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ planTier: 'bronze' }),
                      });
                      setTenant({ ...tenant, planTier: 'bronze' });
                      setUpgradeModalOpen(false);
                      setBanner({ kind: 'ok', text: 'پلن سالن به برنزی تغییر یافت ✓' });
                    }}
                    className="mt-4 w-full py-1.5 rounded-lg bg-neutral-800 hover:bg-neutral-700 text-neutral-200 text-[11px] font-bold disabled:opacity-40"
                  >
                    {tenant.planTier === 'bronze' ? 'پلن فعلی شما' : 'انتخاب برنزی'}
                  </button>
                </div>

                {/* پلن نقره‌ای */}
                <div className={`p-4 rounded-xl border flex flex-col justify-between ${
                  tenant.planTier === 'silver' ? 'bg-amber-500/10 border-amber-400' : 'bg-neutral-950 border-neutral-800'
                }`}>
                  <div>
                    <h4 className="text-sm font-bold text-neutral-100 mb-1">🥈 پلن نقره‌ای</h4>
                    <p className="text-[11px] text-amber-400 font-bold mb-3">۱,۵۰۰,۰۰۰ تومان / ماه</p>
                    <ul className="text-[10px] text-neutral-400 space-y-1.5 list-disc list-inside">
                      <li>ابرو + لب + خط چشم</li>
                      <li>۲۵۰ پیش‌نمایش در ماه</li>
                      <li>بدون واترمارک</li>
                      <li>چت‌بات هوشمند مشاور</li>
                    </ul>
                  </div>
                  <button
                    disabled={tenant.planTier === 'silver'}
                    onClick={async () => {
                      await adminFetch('/api/admin/tenant', {
                        method: 'PATCH',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ planTier: 'silver' }),
                      });
                      setTenant({ ...tenant, planTier: 'silver' });
                      setUpgradeModalOpen(false);
                      setBanner({ kind: 'ok', text: 'پلن سالن به نقره‌ای ارتقا یافت ✓' });
                    }}
                    className="mt-4 w-full py-1.5 rounded-lg bg-neutral-800 hover:bg-neutral-700 text-neutral-200 text-[11px] font-bold disabled:opacity-40"
                  >
                    {tenant.planTier === 'silver' ? 'پلن فعلی شما' : 'ارتقا به نقره‌ای'}
                  </button>
                </div>

                {/* پلن طلایی */}
                <div className={`p-4 rounded-xl border flex flex-col justify-between relative overflow-hidden ${
                  tenant.planTier === 'gold' ? 'bg-amber-500/15 border-amber-400' : 'bg-neutral-950 border-neutral-800'
                }`}>
                  <div className="absolute top-0 right-0 px-2 py-0.5 bg-amber-500 text-neutral-950 text-[9px] font-bold rounded-bl-lg">
                    پیشنهادی VIP
                  </div>
                  <div>
                    <h4 className="text-sm font-bold text-neutral-100 mb-1">🥇 پلن طلایی VIP</h4>
                    <p className="text-[11px] text-amber-300 font-bold mb-3">۳,۰۰۰,۰۰۰ تومان / ماه</p>
                    <ul className="text-[10px] text-neutral-300 space-y-1.5 list-disc list-inside">
                      <li>هر ۴ خدمت (شامل ریمو)</li>
                      <li>پیش‌نمایش نامحدود</li>
                      <li>اسکن بیومتریک لیزری</li>
                      <li>کارت VIP متالیک + Confetti</li>
                      <li>آپلود نمونه‌کارهای سالن</li>
                      <li>شخصی‌سازی نام مشاور</li>
                    </ul>
                  </div>
                  <button
                    disabled={tenant.planTier === 'gold'}
                    onClick={async () => {
                      await adminFetch('/api/admin/tenant', {
                        method: 'PATCH',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ planTier: 'gold' }),
                      });
                      setTenant({ ...tenant, planTier: 'gold' });
                      setUpgradeModalOpen(false);
                      setBanner({ kind: 'ok', text: 'پلن سالن به طلایی VIP ارتقا یافت ✓' });
                    }}
                    className="mt-4 w-full py-1.5 rounded-lg bg-gradient-to-r from-amber-500 to-amber-600 hover:from-amber-400 text-neutral-950 text-[11px] font-bold disabled:opacity-40"
                  >
                    {tenant.planTier === 'gold' ? 'پلن فعال شما' : 'ارتقا به طلایی VIP'}
                  </button>
                </div>
              </div>

              <div className="p-3.5 rounded-xl bg-neutral-950 border border-neutral-800 text-center">
                <p className="text-[11px] text-neutral-400">
                  جهت پرداخت وجه و تایید فیش واریز، با واحد پشتیبانی مالی تماس حاصل فرمایید.
                </p>
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}

function StatCard({ title, value, icon }: { title: string; value: number; icon: string }) {
  return (
    <div className="p-4 rounded-2xl bg-neutral-900/70 border border-neutral-800">
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs text-neutral-400">{title}</span>
        <span className="text-lg">{icon}</span>
      </div>
      <p className="text-2xl font-black text-amber-400">{faNumber(value)}</p>
    </div>
  );
}
