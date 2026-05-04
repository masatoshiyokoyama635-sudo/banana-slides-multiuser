import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ArrowUp, FileText, Home, Key, RotateCcw, Save } from 'lucide-react';
import { useT } from '@/hooks/useT';
import { Button, Card, Input, Loading, LogoutButton, useConfirm, useToast } from '@/components/shared';
import * as api from '@/api/endpoints';
import type { Settings as SettingsType } from '@/types';

const settingsI18n = {
  zh: {
    nav: { backToHome: '返回首页' },
    settings: {
      title: '系统设置',
      subtitle: '配置你的大模型 API Key',
      sections: {
        apiConfig: 'API Key 配置',
        apiConfigDesc: '中转站和模型已由后台统一配置，用户只需填写自己的 API Key',
        serviceTest: '服务测试',
      },
      fields: {
        apiKey: 'API Key',
        apiKeyPlaceholder: '输入新的 API Key',
        apiKeyDesc: '留空则保持当前设置不变，输入新值则更新',
        apiKeySet: '已设置（长度: {{length}}）',
      },
      serviceTest: {
        description: '提前验证当前 API Key 是否可用于文本、图片识别和图像生成。',
        tip: '图像生成测试可能需要数分钟，请耐心等待。',
        startTest: '开始测试',
        testing: '测试中...',
        testTimeout: '测试超时，请重试',
        testFailed: '测试失败',
        tests: {
          textModel: { title: '文本生成模型', description: '发送短提示词，验证文本模型与 API Key' },
          captionModel: { title: '图片识别模型', description: '生成测试图片并请求模型输出描述' },
          imageModel: { title: '图像生成模型', description: '生成演示文稿背景图，验证图像生成服务' },
        },
        results: {
          modelReply: '模型回复：{{reply}}',
          captionDesc: '识别描述：{{caption}}',
          imageSize: '输出尺寸：{{width}}x{{height}}',
        },
      },
      actions: { save: '保存设置', saving: '保存中...', resetToDefault: '清除 API Key' },
      messages: {
        loadFailed: '加载设置失败',
        saveSuccess: '设置保存成功',
        saveFailed: '保存设置失败',
        noApiKeyChange: '未填写新的 API Key，当前设置保持不变',
        resetConfirm: '将清除你当前保存的 API Key，确定继续吗？',
        resetTitle: '确认清除 API Key',
        resetSuccess: 'API Key 已清除',
        resetFailed: '清除 API Key 失败',
        resetConfirmBtn: '确定清除',
        resetCancelBtn: '取消',
        unknownError: '未知错误',
        testServiceTip: '建议在本页底部进行服务测试，验证 API Key 是否可用',
        testSuccess: '测试成功',
      },
    },
    common: { loading: '加载中...' },
  },
  en: {
    nav: { backToHome: 'Back to Home' },
    settings: {
      title: 'Settings',
      subtitle: 'Configure your model API key',
      sections: {
        apiConfig: 'API Key Configuration',
        apiConfigDesc: 'The proxy endpoint and models are managed by the server; users only need to enter their API key',
        serviceTest: 'Service Test',
      },
      fields: {
        apiKey: 'API Key',
        apiKeyPlaceholder: 'Enter new API Key',
        apiKeyDesc: 'Leave empty to keep current setting, enter a new value to update',
        apiKeySet: 'Set (length: {{length}})',
      },
      serviceTest: {
        description: 'Verify that the current API key works for text, image captioning, and image generation.',
        tip: 'Image generation tests may take several minutes. Please wait patiently.',
        startTest: 'Start Test',
        testing: 'Testing...',
        testTimeout: 'Test timeout, please retry',
        testFailed: 'Test failed',
        tests: {
          textModel: { title: 'Text Generation Model', description: 'Send a short prompt to verify the text model and API key' },
          captionModel: { title: 'Image Caption Model', description: 'Use a test image and request a model description' },
          imageModel: { title: 'Image Generation Model', description: 'Generate a presentation background to verify image generation' },
        },
        results: {
          modelReply: 'Model reply: {{reply}}',
          captionDesc: 'Caption: {{caption}}',
          imageSize: 'Output size: {{width}}x{{height}}',
        },
      },
      actions: { save: 'Save Settings', saving: 'Saving...', resetToDefault: 'Clear API Key' },
      messages: {
        loadFailed: 'Failed to load settings',
        saveSuccess: 'Settings saved successfully',
        saveFailed: 'Failed to save settings',
        noApiKeyChange: 'No new API key entered; current settings are unchanged',
        resetConfirm: 'This will clear your saved API key. Continue?',
        resetTitle: 'Confirm API Key Clear',
        resetSuccess: 'API key cleared',
        resetFailed: 'Failed to clear API key',
        resetConfirmBtn: 'Clear',
        resetCancelBtn: 'Cancel',
        unknownError: 'Unknown error',
        testServiceTip: 'Run the service tests below to verify whether the API key is usable',
        testSuccess: 'Test passed',
      },
    },
    common: { loading: 'Loading...' },
  },
};

const initialFormData = {
  api_key: '',
};

type TestStatus = 'idle' | 'loading' | 'success' | 'error';

interface ServiceTestState {
  status: TestStatus;
  message?: string;
  detail?: string;
}

const apiKeyPlaceholder = (settings: SettingsType | null, t: ReturnType<typeof useT>) => {
  if (settings && settings.api_key_length > 0) {
    return t('settings.fields.apiKeySet', { length: settings.api_key_length });
  }
  return t('settings.fields.apiKeyPlaceholder');
};

export const Settings: React.FC = () => {
  const t = useT(settingsI18n);
  const { show, ToastContainer } = useToast();
  const { confirm, ConfirmDialog } = useConfirm();
  const [settings, setSettings] = useState<SettingsType | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [formData, setFormData] = useState(initialFormData);
  const [serviceTestStates, setServiceTestStates] = useState<Record<string, ServiceTestState>>({});

  useEffect(() => {
    loadSettings();
  }, []);

  const loadSettings = async () => {
    setIsLoading(true);
    try {
      const response = await api.getSettings();
      if (response.data) {
        setSettings(response.data);
        setFormData(initialFormData);
        sessionStorage.setItem('banana-settings', JSON.stringify(response.data));
      }
    } catch (error: any) {
      console.error('加载设置失败:', error);
      show({
        message: `${t('settings.messages.loadFailed')}: ${error?.message || t('settings.messages.unknownError')}`,
        type: 'error',
      });
    } finally {
      setIsLoading(false);
    }
  };

  const handleSave = async () => {
    const apiKey = formData.api_key.trim();
    if (!apiKey) {
      show({ message: t('settings.messages.noApiKeyChange'), type: 'info' });
      return;
    }

    setIsSaving(true);
    try {
      const payload: Parameters<typeof api.updateSettings>[0] = { api_key: apiKey };
      const response = await api.updateSettings(payload);
      if (response.data) {
        setSettings(response.data);
        sessionStorage.setItem('banana-settings', JSON.stringify(response.data));
        setFormData(initialFormData);
        show({ message: t('settings.messages.saveSuccess'), type: 'success' });
        show({ message: t('settings.messages.testServiceTip'), type: 'info' });
      }
    } catch (error: any) {
      console.error('保存设置失败:', error);
      show({
        message: `${t('settings.messages.saveFailed')}: ${error?.response?.data?.error?.message || error?.message || t('settings.messages.unknownError')}`,
        type: 'error',
      });
    } finally {
      setIsSaving(false);
    }
  };

  const handleReset = () => {
    confirm(
      t('settings.messages.resetConfirm'),
      async () => {
        setIsSaving(true);
        try {
          const response = await api.resetSettings();
          if (response.data) {
            setSettings(response.data);
            setFormData(initialFormData);
            show({ message: t('settings.messages.resetSuccess'), type: 'success' });
          }
        } catch (error: any) {
          console.error('重置设置失败:', error);
          show({
            message: `${t('settings.messages.resetFailed')}: ${error?.message || t('settings.messages.unknownError')}`,
            type: 'error',
          });
        } finally {
          setIsSaving(false);
        }
      },
      {
        title: t('settings.messages.resetTitle'),
        confirmText: t('settings.messages.resetConfirmBtn'),
        cancelText: t('settings.messages.resetCancelBtn'),
        variant: 'warning',
      }
    );
  };

  const updateServiceTest = (key: string, nextState: ServiceTestState) => {
    setServiceTestStates(prev => ({ ...prev, [key]: nextState }));
  };

  const handleServiceTest = async (
    key: string,
    action: (settings?: api.TestSettingsOverride) => Promise<{ data?: { task_id?: string } }>,
    formatDetail: (data: Record<string, unknown>) => string
  ) => {
    updateServiceTest(key, { status: 'loading' });
    try {
      const apiKey = formData.api_key.trim();
      const testSettings = apiKey ? { api_key: apiKey } : undefined;
      const response = await action(testSettings);
      const taskId = response.data?.task_id;
      if (!taskId) {
        throw new Error(t('settings.serviceTest.testFailed'));
      }

      let isActive = true;
      let pollInterval: ReturnType<typeof setInterval> | undefined;
      let timeoutId: ReturnType<typeof setTimeout> | undefined;
      const finish = (nextState: ServiceTestState, toastMsg: string, toastType: 'success' | 'error') => {
        if (!isActive) return;
        isActive = false;
        if (pollInterval) clearInterval(pollInterval);
        if (timeoutId) clearTimeout(timeoutId);
        updateServiceTest(key, nextState);
        show({ message: toastMsg, type: toastType });
      };

      pollInterval = setInterval(async () => {
        try {
          const statusResponse = await api.getTestStatus(taskId);
          const statusData = statusResponse.data;
          if (!statusData) {
            throw new Error(t('settings.serviceTest.testFailed'));
          }
          const taskStatus = statusData.status;

          if (taskStatus === 'COMPLETED') {
            const result = (statusData.result || {}) as Record<string, unknown>;
            const detail = formatDetail(result);
            const message = statusData.message || t('settings.messages.testSuccess');
            finish({ status: 'success', message, detail }, message, 'success');
          } else if (taskStatus === 'FAILED') {
            const errorMessage = statusData.error || t('settings.serviceTest.testFailed');
            finish({ status: 'error', message: errorMessage }, `${t('settings.serviceTest.testFailed')}: ${errorMessage}`, 'error');
          }
        } catch (pollError: any) {
          const errorMessage = pollError?.response?.data?.error?.message || pollError?.message || t('settings.serviceTest.testFailed');
          finish({ status: 'error', message: errorMessage }, `${t('settings.serviceTest.testFailed')}: ${errorMessage}`, 'error');
        }
      }, 2000);

      timeoutId = setTimeout(() => {
        finish({ status: 'error', message: t('settings.serviceTest.testTimeout') }, t('settings.serviceTest.testTimeout'), 'error');
      }, 600000);
    } catch (error: any) {
      const errorMessage = error?.response?.data?.error?.message || error?.message || t('settings.messages.unknownError');
      updateServiceTest(key, { status: 'error', message: errorMessage });
      show({ message: `${t('settings.serviceTest.testFailed')}: ${errorMessage}`, type: 'error' });
    }
  };

  const serviceTests = [
    {
      key: 'text-model',
      titleKey: 'settings.serviceTest.tests.textModel.title',
      descriptionKey: 'settings.serviceTest.tests.textModel.description',
      action: api.testTextModel,
      formatDetail: (data: Record<string, unknown>) => {
        const reply = typeof data.reply === 'string' ? data.reply : '';
        return reply ? t('settings.serviceTest.results.modelReply', { reply }) : '';
      },
    },
    {
      key: 'caption-model',
      titleKey: 'settings.serviceTest.tests.captionModel.title',
      descriptionKey: 'settings.serviceTest.tests.captionModel.description',
      action: api.testCaptionModel,
      formatDetail: (data: Record<string, unknown>) => {
        const caption = typeof data.caption === 'string' ? data.caption : '';
        return caption ? t('settings.serviceTest.results.captionDesc', { caption }) : '';
      },
    },
    {
      key: 'image-model',
      titleKey: 'settings.serviceTest.tests.imageModel.title',
      descriptionKey: 'settings.serviceTest.tests.imageModel.description',
      action: api.testImageModel,
      formatDetail: (data: Record<string, unknown>) => {
        const imageSize = data.image_size;
        if (Array.isArray(imageSize) && imageSize.length >= 2) {
          return t('settings.serviceTest.results.imageSize', { width: String(imageSize[0]), height: String(imageSize[1]) });
        }
        return '';
      },
    },
  ];

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loading message={t('common.loading')} />
      </div>
    );
  }

  return (
    <>
      <ToastContainer />
      {ConfirmDialog}
      <div className="space-y-8">
        <div data-testid="global-api-config-section">
          <h2 className="text-xl font-semibold text-gray-900 dark:text-foreground-primary mb-1 flex items-center">
            <Key size={20} />
            <span className="ml-2">{t('settings.sections.apiConfig')}</span>
          </h2>
          <p className="text-sm text-gray-500 dark:text-foreground-tertiary mb-4">{t('settings.sections.apiConfigDesc')}</p>
          <div className="p-4 bg-gray-50 dark:bg-background-primary border border-gray-200 dark:border-border-primary rounded-lg space-y-3">
            <Input
              label={t('settings.fields.apiKey')}
              type="password"
              placeholder={apiKeyPlaceholder(settings, t)}
              value={formData.api_key}
              onChange={(event) => setFormData(prev => ({ ...prev, api_key: event.target.value }))}
            />
            <p className="text-sm text-gray-500 dark:text-foreground-tertiary">{t('settings.fields.apiKeyDesc')}</p>
          </div>
        </div>

        <div className="space-y-4">
          <h2 className="text-xl font-semibold text-gray-900 dark:text-foreground-primary mb-2 flex items-center">
            <FileText size={20} />
            <span className="ml-2">{t('settings.sections.serviceTest')}</span>
          </h2>
          <p className="text-sm text-gray-500 dark:text-foreground-tertiary">{t('settings.serviceTest.description')}</p>
          <div className="p-3 bg-yellow-50 dark:bg-background-primary border border-yellow-200 dark:border-yellow-700 rounded-lg">
            <p className="text-sm text-gray-700 dark:text-foreground-secondary">{t('settings.serviceTest.tip')}</p>
          </div>
          <div className="space-y-4">
            {serviceTests.map((item) => {
              const testState = serviceTestStates[item.key] || { status: 'idle' as TestStatus };
              const isLoadingTest = testState.status === 'loading';
              return (
                <div
                  key={item.key}
                  className="p-4 bg-gray-50 dark:bg-background-primary border border-gray-200 dark:border-border-primary rounded-lg space-y-2"
                >
                  <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
                    <div>
                      <div className="text-base font-semibold text-gray-800 dark:text-foreground-primary">{t(item.titleKey)}</div>
                      <div className="text-sm text-gray-500 dark:text-foreground-tertiary">{t(item.descriptionKey)}</div>
                    </div>
                    <Button
                      variant="secondary"
                      size="sm"
                      loading={isLoadingTest}
                      onClick={() => handleServiceTest(item.key, item.action, item.formatDetail)}
                    >
                      {isLoadingTest ? t('settings.serviceTest.testing') : t('settings.serviceTest.startTest')}
                    </Button>
                  </div>
                  {testState.status === 'success' && (
                    <p className="text-sm text-green-600">
                      {testState.message}{testState.detail ? `｜${testState.detail}` : ''}
                    </p>
                  )}
                  {testState.status === 'error' && (
                    <p className="text-sm text-red-600">{testState.message}</p>
                  )}
                </div>
              );
            })}
          </div>
        </div>

        <div className="flex items-center justify-between pt-4 border-t border-gray-200 dark:border-border-primary">
          <Button
            variant="secondary"
            icon={<RotateCcw size={18} />}
            onClick={handleReset}
            disabled={isSaving}
          >
            {t('settings.actions.resetToDefault')}
          </Button>
          <Button
            variant="primary"
            icon={<Save size={18} />}
            onClick={handleSave}
            loading={isSaving}
          >
            {isSaving ? t('settings.actions.saving') : t('settings.actions.save')}
          </Button>
        </div>
      </div>
    </>
  );
};

const SCROLL_SHOW_THRESHOLD = 300;

export const SettingsPage: React.FC = () => {
  const navigate = useNavigate();
  const t = useT(settingsI18n);
  const [showTop, setShowTop] = useState(false);

  useEffect(() => {
    const onScroll = () => setShowTop(window.scrollY > SCROLL_SHOW_THRESHOLD);
    window.addEventListener('scroll', onScroll, { passive: true });
    return () => window.removeEventListener('scroll', onScroll);
  }, []);

  return (
    <div className="min-h-screen bg-gradient-to-br from-banana-50 dark:from-background-primary to-yellow-50 dark:to-background-primary">
      <div className="container mx-auto px-4 py-8 max-w-4xl">
        <Card className="p-6 md:p-8">
          <div className="space-y-8">
            <div className="flex items-center justify-between pb-6 border-b border-gray-200 dark:border-border-primary">
              <div className="flex items-center">
                <Button
                  variant="secondary"
                  icon={<Home size={18} />}
                  onClick={() => navigate('/')}
                  className="mr-4"
                >
                  {t('nav.backToHome')}
                </Button>
                <div>
                  <h1 className="text-2xl font-bold text-gray-900 dark:text-foreground-primary">{t('settings.title')}</h1>
                  <p className="text-sm text-gray-500 dark:text-foreground-tertiary mt-1">{t('settings.subtitle')}</p>
                </div>
              </div>
              <LogoutButton />
            </div>

            <Settings />
          </div>
        </Card>
      </div>

      {showTop && (
        <button
          data-testid="back-to-top-button"
          aria-label="Back to top"
          title="Back to top"
          onClick={() => window.scrollTo({ top: 0, behavior: 'smooth' })}
          className="fixed bottom-6 right-6 p-3 rounded-full bg-banana-500 text-white shadow-lg hover:bg-banana-600 transition-all z-50"
        >
          <ArrowUp size={20} />
        </button>
      )}
    </div>
  );
};
