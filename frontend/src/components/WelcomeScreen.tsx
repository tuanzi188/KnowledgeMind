import React, { useState, useEffect } from 'react'
import { Upload, Button, Modal, Typography, Steps } from 'antd'
import {
  UploadOutlined,
  SearchOutlined,
  QuestionCircleOutlined,
  FileTextOutlined,
  ThunderboltOutlined,
  SafetyCertificateOutlined,
  CloseOutlined,
} from '@ant-design/icons'

const { Title, Text, Paragraph } = Typography

interface WelcomeScreenProps {
  hasDocuments?: boolean
  documentCount?: number
  onUpload: (file: File) => Promise<boolean | void>
  onQuickQuestion?: (question: string) => void
}

const quickQuestions = [
  '请总结已上传文档的核心内容',
  '文档中提到了哪些关键数据？',
  '请对比不同文档中的观点差异',
  '基于文档，给我一个执行摘要',
]

const WelcomeScreen: React.FC<WelcomeScreenProps> = ({
  hasDocuments = false,
  documentCount = 0,
  onUpload,
  onQuickQuestion,
}) => {
  const [onboardingOpen, setOnboardingOpen] = useState(false)

  useEffect(() => {
    const dismissed = localStorage.getItem('km_onboarding_dismissed')
    if (!dismissed) {
      setOnboardingOpen(true)
    }
  }, [])

  const dismissOnboarding = () => {
    setOnboardingOpen(false)
    localStorage.setItem('km_onboarding_dismissed', 'true')
  }

  // 线性几何脑型图标
  const BrainIcon = () => (
    <svg
      width="56"
      height="56"
      viewBox="0 0 56 56"
      fill="none"
      style={{ opacity: 0.85 }}
    >
      {/* 大脑左半球 */}
      <path
        d="M28 6C18 6 10 14 10 24c0 5 2 9 5 12-2 3-3 7-2 10 2 5 7 8 12 6 2 0 4-1 5-2 3 1 6 2 9 1 4-1 7-4 8-8 1-3 0-6-2-9 3-3 5-7 5-12 0-10-8-18-18-18z"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      {/* 脑回 */}
      <path
        d="M18 22c1-2 3-3 5-3M22 16c2-1 4-1 6 0M33 16c2-1 4-1 6 0M38 22c1-2 3-3 5-3M18 28c2 2 4 2 6 1M33 28c2 2 4 2 6 1"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
      />
      {/* 中央连接线 */}
      <path
        d="M28 20v12M26 26h4"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
      />
    </svg>
  )

  // 已有文档的页面
  if (hasDocuments) {
    return (
      <div
        className="animate-fade-in-up"
        style={{
          maxWidth: 680,
          margin: '0 auto',
          padding: '40px 16px',
        }}
      >
        {/* 文档概览 */}
        <div
          style={{
            textAlign: 'center',
            marginBottom: 32,
          }}
        >
          <div style={{ color: 'var(--color-primary)', marginBottom: 12 }}>
            <BrainIcon />
          </div>
          <Title level={4} style={{ margin: '0 0 4px', color: 'var(--color-text)' }}>
            知识库已就绪
          </Title>
          <Text type="secondary">
            已上传 {documentCount} 篇文档，可以开始提问了
          </Text>
        </div>

        {/* 快捷提问模板 */}
        <div style={{ marginBottom: 16 }}>
          <Text
            style={{
              fontSize: 12,
              color: 'var(--color-text-tertiary)',
              marginBottom: 8,
              display: 'block',
              paddingLeft: 4,
            }}
          >
            快速提问
          </Text>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
            {quickQuestions.map((q, i) => (
              <div
                key={i}
                onClick={() => onQuickQuestion?.(q)}
                style={{
                  padding: '8px 16px',
                  borderRadius: 'var(--radius-lg)',
                  border: '1px solid var(--color-border)',
                  fontSize: 13,
                  color: 'var(--color-text-secondary)',
                  cursor: 'pointer',
                  transition: 'all var(--transition-fast)',
                  background: 'var(--color-bg-white)',
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.borderColor = 'var(--color-primary)'
                  e.currentTarget.style.color = 'var(--color-primary)'
                  e.currentTarget.style.background = 'var(--color-primary-light)'
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.borderColor = 'var(--color-border)'
                  e.currentTarget.style.color = 'var(--color-text-secondary)'
                  e.currentTarget.style.background = 'var(--color-bg-white)'
                }}
              >
                {q}
              </div>
            ))}
          </div>
        </div>

        {/* 继续上传 */}
        <Upload
          beforeUpload={(file) => {
            onUpload(file)
            return false
          }}
          showUploadList={false}
          accept=".pdf,.txt,.md,.docx,.xlsx,.csv"
        >
          <Button
            type="dashed"
            icon={<UploadOutlined />}
            block
            size="large"
            className="btn-hover"
            style={{
              height: 48,
              borderColor: 'var(--color-border)',
              color: 'var(--color-text-secondary)',
            }}
          >
            继续上传文档
          </Button>
        </Upload>
      </div>
    )
  }

  // 无文档的欢迎页
  return (
    <>
      <div
        className="animate-fade-in-up"
        style={{
          maxWidth: 720,
          margin: '0 auto',
          padding: '60px 16px 40px',
        }}
      >
        {/* 品牌标识区 */}
        <div style={{ textAlign: 'center', marginBottom: 40 }}>
          <div style={{ color: 'var(--color-primary)', marginBottom: 16 }}>
            <BrainIcon />
          </div>
          <Title
            level={3}
            style={{
              margin: '0 0 8px',
              color: 'var(--color-text)',
              fontWeight: 600,
            }}
          >
            欢迎使用 KnowledgeMind
          </Title>
          <Paragraph
            type="secondary"
            style={{ fontSize: 14, margin: 0 }}
          >
            上传企业文档，即刻获得基于 AI 的智能知识检索与问答
          </Paragraph>
        </div>

        {/* 三大功能卡片 */}
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(3, 1fr)',
            gap: 16,
            marginBottom: 32,
          }}
        >
          {/* 上传文档 - 核心操作卡片 */}
          <Upload
            beforeUpload={(file) => {
              onUpload(file)
              return false
            }}
            showUploadList={false}
            accept=".pdf,.txt,.md,.docx,.xlsx,.csv"
          >
            <div
              className="card-hover"
              style={{
                padding: '24px 20px',
                borderRadius: 'var(--radius-lg)',
                border: '2px solid var(--color-primary)',
                background: 'var(--color-primary-light)',
                textAlign: 'center',
                cursor: 'pointer',
                position: 'relative',
                overflow: 'hidden',
              }}
            >
              <div
                style={{
                  position: 'absolute',
                  top: -20,
                  right: -20,
                  width: 60,
                  height: 60,
                  borderRadius: '50%',
                  background: 'var(--color-primary)',
                  opacity: 0.06,
                }}
              />
              <UploadOutlined
                style={{ fontSize: 28, color: 'var(--color-primary)', marginBottom: 12 }}
              />
              <div style={{ fontSize: 15, fontWeight: 600, color: 'var(--color-primary)', marginBottom: 4 }}>
                上传文档
              </div>
              <div style={{ fontSize: 12, color: 'var(--color-text-secondary)', lineHeight: 1.5 }}>
                支持 PDF、Word、Excel
                <br />
                TXT、Markdown 等格式
              </div>
            </div>
          </Upload>

          {/* 智能检索 - 静态展示 */}
          <div
            style={{
              padding: '24px 20px',
              borderRadius: 'var(--radius-lg)',
              border: '1px solid var(--color-border-light)',
              background: 'var(--color-bg-white)',
              textAlign: 'center',
              transition: 'all var(--transition-normal)',
            }}
          >
            <SearchOutlined
              style={{ fontSize: 28, color: 'var(--color-text-tertiary)', marginBottom: 12 }}
            />
            <div style={{ fontSize: 15, fontWeight: 600, color: 'var(--color-text)', marginBottom: 4 }}>
              智能检索
            </div>
            <div style={{ fontSize: 12, color: 'var(--color-text-secondary)', lineHeight: 1.5 }}>
              语义级深度搜索
              <br />
              毫秒级精准定位
            </div>
          </div>

          {/* 溯源问答 - 静态展示 */}
          <div
            style={{
              padding: '24px 20px',
              borderRadius: 'var(--radius-lg)',
              border: '1px solid var(--color-border-light)',
              background: 'var(--color-bg-white)',
              textAlign: 'center',
              transition: 'all var(--transition-normal)',
            }}
          >
            <QuestionCircleOutlined
              style={{ fontSize: 28, color: 'var(--color-text-tertiary)', marginBottom: 12 }}
            />
            <div style={{ fontSize: 15, fontWeight: 600, color: 'var(--color-text)', marginBottom: 4 }}>
              溯源问答
            </div>
            <div style={{ fontSize: 12, color: 'var(--color-text-secondary)', lineHeight: 1.5 }}>
              答案可追溯原文
              <br />
              附带置信度评分
            </div>
          </div>
        </div>

        {/* 底部能力标签 */}
        <div style={{ display: 'flex', justifyContent: 'center', gap: 24, flexWrap: 'wrap' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, color: 'var(--color-text-tertiary)', fontSize: 12 }}>
            <ThunderboltOutlined /> DeepSeek RAG 引擎
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, color: 'var(--color-text-tertiary)', fontSize: 12 }}>
            <SafetyCertificateOutlined /> 企业级数据安全
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, color: 'var(--color-text-tertiary)', fontSize: 12 }}>
            <FileTextOutlined /> 多格式文档解析
          </div>
        </div>
      </div>

      {/* 新手引导浮层 */}
      <Modal
        title={null}
        open={onboardingOpen}
        onCancel={dismissOnboarding}
        footer={null}
        width={480}
        centered
        closeIcon={<CloseOutlined style={{ fontSize: 14 }} />}
        styles={{
          body: { padding: '32px 24px 24px' },
        }}
      >
        <div style={{ textAlign: 'center', marginBottom: 24 }}>
          <div style={{ color: 'var(--color-primary)', marginBottom: 12 }}>
            <BrainIcon />
          </div>
          <Title level={4} style={{ margin: '0 0 4px' }}>
            快速上手
          </Title>
          <Text type="secondary" style={{ fontSize: 13 }}>
            三步开启智能知识问答
          </Text>
        </div>

        <Steps
          direction="vertical"
          size="small"
          current={-1}
          items={[
            {
              title: '上传文档',
              description: '点击「上传文档」按钮，选择 PDF、Word、Excel 或 TXT 文件上传到知识库',
              icon: <UploadOutlined />,
            },
            {
              title: '检索知识库',
              description: '系统自动解析文档内容，构建语义索引，支持毫秒级精准检索',
              icon: <SearchOutlined />,
            },
            {
              title: '提问获取溯源回答',
              description: '在输入框输入问题，AI 将基于文档内容给出可追溯原文的精准回答',
              icon: <QuestionCircleOutlined />,
            },
          ]}
          style={{ marginBottom: 24 }}
        />

        <Button
          type="primary"
          block
          onClick={dismissOnboarding}
          className="btn-hover"
        >
          开始使用
        </Button>
      </Modal>
    </>
  )
}

export default WelcomeScreen