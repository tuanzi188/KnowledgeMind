import React, { useEffect, useState } from 'react'
import {
  Card,
  Col,
  Row,
  Statistic,
  Tabs,
  Table,
  Select,
  Spin,
  Alert,
  Typography,
  Button,
  Space,
  Tag,
} from 'antd'
import { ReloadOutlined, BarChartOutlined, FileTextOutlined, CommentOutlined, ToolOutlined, ShareAltOutlined } from '@ant-design/icons'
import {
  getAnalyticsOverview,
  analyzeDocuments,
  analyzeConversations,
  analyzeTasks,
  analyzeGraph,
  AnalyticsResponse,
} from '../api/client'

const { Title, Text } = Typography
const { TabPane } = Tabs
const { Option } = Select

interface LoadingState {
  overview: boolean
  documents: boolean
  conversations: boolean
  tasks: boolean
  graph: boolean
}

interface ErrorState {
  overview?: string
  documents?: string
  conversations?: string
  tasks?: string
  graph?: string
}

const DEFAULT_LOADING: LoadingState = {
  overview: false,
  documents: false,
  conversations: false,
  tasks: false,
  graph: false,
}

const DEFAULT_ERRORS: ErrorState = {}

const AnalyticsDashboard: React.FC = () => {
  const [data, setData] = useState<Record<string, AnalyticsResponse>>({})
  const [loading, setLoading] = useState<LoadingState>(DEFAULT_LOADING)
  const [errors, setErrors] = useState<ErrorState>(DEFAULT_ERRORS)
  const [activeTab, setActiveTab] = useState('overview')
  const [groupBy, setGroupBy] = useState<Record<string, string>>({
    documents: 'file_type',
    conversations: 'day',
    tasks: 'status',
    graph: '',
  })

  const setMetricLoading = (metric: keyof LoadingState, value: boolean) => {
    setLoading((prev) => ({ ...prev, [metric]: value }))
  }

  const setMetricError = (metric: keyof ErrorState, value?: string) => {
    setErrors((prev) => ({ ...prev, [metric]: value }))
  }

  const loadOverview = async () => {
    setMetricLoading('overview', true)
    setMetricError('overview', undefined)
    try {
      const result = await getAnalyticsOverview()
      setData((prev) => ({ ...prev, overview: result }))
    } catch (err: any) {
      setMetricError('overview', err.message || '加载失败')
    } finally {
      setMetricLoading('overview', false)
    }
  }

  const loadDocuments = async (group: string = groupBy.documents) => {
    setMetricLoading('documents', true)
    setMetricError('documents', undefined)
    try {
      const result = await analyzeDocuments({ group_by: group })
      setData((prev) => ({ ...prev, documents: result }))
    } catch (err: any) {
      setMetricError('documents', err.message || '加载失败')
    } finally {
      setMetricLoading('documents', false)
    }
  }

  const loadConversations = async (group: string = groupBy.conversations) => {
    setMetricLoading('conversations', true)
    setMetricError('conversations', undefined)
    try {
      const result = await analyzeConversations({ group_by: group })
      setData((prev) => ({ ...prev, conversations: result }))
    } catch (err: any) {
      setMetricError('conversations', err.message || '加载失败')
    } finally {
      setMetricLoading('conversations', false)
    }
  }

  const loadTasks = async (group: string = groupBy.tasks) => {
    setMetricLoading('tasks', true)
    setMetricError('tasks', undefined)
    try {
      const result = await analyzeTasks({ group_by: group })
      setData((prev) => ({ ...prev, tasks: result }))
    } catch (err: any) {
      setMetricError('tasks', err.message || '加载失败')
    } finally {
      setMetricLoading('tasks', false)
    }
  }

  const loadGraph = async () => {
    setMetricLoading('graph', true)
    setMetricError('graph', undefined)
    try {
      const result = await analyzeGraph({ top_k: 20 })
      setData((prev) => ({ ...prev, graph: result }))
    } catch (err: any) {
      setMetricError('graph', err.message || '加载失败')
    } finally {
      setMetricLoading('graph', false)
    }
  }

  useEffect(() => {
    loadOverview()
  }, [])

  const handleTabChange = (key: string) => {
    setActiveTab(key)
    if (key === 'documents' && !data.documents) loadDocuments()
    if (key === 'conversations' && !data.conversations) loadConversations()
    if (key === 'tasks' && !data.tasks) loadTasks()
    if (key === 'graph' && !data.graph) loadGraph()
  }

  const renderSummaryCards = (metric: string) => {
    const metricData = data[metric]
    if (!metricData) return null
    const summary = metricData.summary || {}
    const entries = Object.entries(summary)
    if (entries.length === 0) return <Text type="secondary">暂无汇总数据</Text>

    return (
      <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
        {entries.slice(0, 8).map(([key, value]) => (
          <Col xs={24} sm={12} md={8} lg={6} key={key}>
            <Card bordered={false} style={{ background: 'var(--color-bg-white)' }}>
              <Statistic
                title={formatLabel(key)}
                value={typeof value === 'number' ? value : String(value)}
                valueStyle={{ fontSize: 24, fontWeight: 600 }}
              />
            </Card>
          </Col>
        ))}
      </Row>
    )
  }

  const renderSeriesTable = (metric: string) => {
    const metricData = data[metric]
    if (!metricData?.series?.length) return <Text type="secondary">暂无分组数据</Text>

    const sample = metricData.series[0]
    const columns = Object.keys(sample).map((key) => ({
      title: formatLabel(key),
      dataIndex: key,
      key,
      render: (value: unknown) => {
        if (typeof value === 'boolean') return <Tag color={value ? 'success' : 'default'}>{value ? '是' : '否'}</Tag>
        if (typeof value === 'number') {
          return Number.isInteger(value) ? value : value.toFixed(2)
        }
        return String(value ?? '-')
      },
    }))

    return (
      <Table
        dataSource={metricData.series}
        columns={columns}
        rowKey={(record, index) => `${metric}-${index}`}
        pagination={{ pageSize: 10 }}
        size="middle"
      />
    )
  }

  const renderTabContent = (
    metric: string,
    groupOptions?: { value: string; label: string }[],
  ) => {
    if (errors[metric as keyof ErrorState]) {
      return (
        <Alert
          message="加载失败"
          description={errors[metric as keyof ErrorState]}
          type="error"
          showIcon
          action={
            <Button size="small" onClick={() => reloadMetric(metric)}>
              重试
            </Button>
          }
        />
      )
    }

    return (
      <Spin spinning={loading[metric as keyof LoadingState]}>
        {groupOptions && (
          <div style={{ marginBottom: 16 }}>
            <Space>
              <Text>分组维度：</Text>
              <Select
                value={groupBy[metric]}
                onChange={(value) => {
                  setGroupBy((prev) => ({ ...prev, [metric]: value }))
                  reloadMetric(metric, value)
                }}
                style={{ width: 160 }}
              >
                {groupOptions.map((opt) => (
                  <Option key={opt.value} value={opt.value}>
                    {opt.label}
                  </Option>
                ))}
              </Select>
            </Space>
          </div>
        )}
        {renderSummaryCards(metric)}
        {renderSeriesTable(metric)}
      </Spin>
    )
  }

  const reloadMetric = (metric: string, value?: string) => {
    if (metric === 'overview') loadOverview()
    if (metric === 'documents') loadDocuments(value)
    if (metric === 'conversations') loadConversations(value)
    if (metric === 'tasks') loadTasks(value)
    if (metric === 'graph') loadGraph()
  }

  const groupOptionsMap: Record<string, { value: string; label: string }[]> = {
    documents: [
      { value: 'file_type', label: '文件类型' },
      { value: 'department', label: '部门' },
      { value: 'classification', label: '密级' },
    ],
    conversations: [
      { value: 'day', label: '按天' },
      { value: 'week', label: '按周' },
      { value: 'month', label: '按月' },
    ],
    tasks: [
      { value: 'status', label: '状态' },
      { value: 'name', label: '任务名' },
    ],
  }

  return (
    <div style={{ padding: 24, maxWidth: 1440, margin: '0 auto' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
        <Title level={3} style={{ margin: 0 }}>
          <BarChartOutlined style={{ marginRight: 12 }} />
          数据分析看板
        </Title>
        <Button icon={<ReloadOutlined />} onClick={() => reloadMetric(activeTab)}>
          刷新
        </Button>
      </div>

      <Tabs activeKey={activeTab} onChange={handleTabChange} type="card">
        <TabPane
          tab={<span><BarChartOutlined /> 总览</span>}
          key="overview"
        >
          {renderTabContent('overview')}
        </TabPane>
        <TabPane
          tab={<span><FileTextOutlined /> 文档分析</span>}
          key="documents"
        >
          {renderTabContent('documents', groupOptionsMap.documents)}
        </TabPane>
        <TabPane
          tab={<span><CommentOutlined /> 对话分析</span>}
          key="conversations"
        >
          {renderTabContent('conversations', groupOptionsMap.conversations)}
        </TabPane>
        <TabPane
          tab={<span><ToolOutlined /> 任务分析</span>}
          key="tasks"
        >
          {renderTabContent('tasks', groupOptionsMap.tasks)}
        </TabPane>
        <TabPane
          tab={<span><ShareAltOutlined /> 知识图谱</span>}
          key="graph"
        >
          {renderTabContent('graph')}
        </TabPane>
      </Tabs>
    </div>
  )
}

function formatLabel(key: string): string {
  const labelMap: Record<string, string> = {
    total_documents: '文档总数',
    total_chunks: '片段总数',
    total_conversations: '对话总数',
    total_turns: '对话轮数',
    total_tasks: '任务总数',
    total_users: '用户总数',
    total_entities: '实体总数',
    total_relations: '关系总数',
    avg_chunks_per_document: '平均片段/文档',
    file_type: '文件类型',
    department: '部门',
    classification: '密级',
    day: '日期',
    week: '周',
    month: '月',
    status: '状态',
    name: '任务名',
    entity: '实体',
    count: '出现次数',
  }
  return labelMap[key] || key.replace(/_/g, ' ')
}

export default AnalyticsDashboard
