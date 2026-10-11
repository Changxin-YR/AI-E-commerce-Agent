<template>
  <PageShell
    title="客服"
    subtitle="草稿、政策与外发预览：系统外部状态保持未提交。"
    :loading="busy"
    :error="error"
    :notice="state.notice"
    :success="successText"
    @retry="load(true)"
  >
    <view class="row">
      <view
        v-for="entry in modes"
        :key="entry.key"
        class="chip"
        :class="{ 'chip--active': mode === entry.key }"
        @tap="mode = entry.key"
      >
        <text>{{ entry.label }}</text>
      </view>
    </view>

    <!-- 客服消息 -->
    <template v-if="mode === 'messages'">
      <view class="field">
        <text class="field__label">查找消息 / 订单号</text>
        <input class="field__input" :value="search" :disabled="busy" @input="search = inputValue($event)" />
      </view>
      <view class="row">
        <ActionButton label="搜索" :disabled="busy" @tap="refreshLists" />
        <ActionButton label="导入客服消息文件" :disabled="busy" @tap="openImports" />
      </view>
      <view v-if="messages.length === 0 && !busy" class="card">
        <text class="hint">没有匹配消息。导入客服消息文件后，这里会显示可处理的对话。</text>
      </view>
      <view v-for="item in messages" :key="item.id" class="card" @tap="choose(item.id)">
        <text class="card__title">{{ item.message_id }} · {{ item.body }}</text>
        <text class="hint">
          {{ labelOf(importChannels, item.channel) }} · {{ labelOf(messageLanguages, item.language) }} ·
          {{ businessTimeText(item.sent_at, zone) }}
        </text>
      </view>
      <view class="row">
        <ActionButton v-if="offset > 0" label="上一页" :disabled="busy" @tap="turn(-50)" />
        <ActionButton v-if="messages.length === 50" label="下一页" :disabled="busy" @tap="turn(50)" />
      </view>

      <template v-if="workspace">
        <text class="section-title">核对消息与订单</text>
        <FactLine label="消息全文" :value="workspace.message.body" />
        <FactLine
          label="消息语言 / 来源渠道"
          :value="`${labelOf(messageLanguages, workspace.message.language)} / ${labelOf(importChannels, workspace.message.channel)}`"
        />
        <FactLine label="消息时间 / 待核验订单" :value="`${businessTimeText(workspace.message.sent_at, zone)} / ${workspace.message.order_id}`" />
        <FactLine
          v-for="order in workspace.orders"
          :key="order.source.row_id"
          label="订单行"
          :value="`${order.order_id} / ${order.line_id} · ${order.sku} · ${order.status} · ${order.fulfillment_status}`"
        />
        <text class="hint">订单号匹配不能证明客户身份。请在原渠道核验客户与全部订单行的关联。</text>
        <view class="row" @tap="toggleOrderVerified">
          <text class="chip" :class="{ 'chip--active': orderVerified }">
            {{ orderVerified ? '已核验' : '未核验' }} · 已人工核验客户与上述全部订单行的关联
          </text>
        </view>

        <text class="section-title">选择适用政策（最多 10 份）</text>
        <text v-if="workspace.policies.length === 0" class="hint">暂无适用政策，将保留人工核实提示。</text>
        <view v-for="policy in workspace.policies" :key="policy.id" class="card" @tap="togglePolicy(policy.id)">
          <text class="chip" :class="{ 'chip--active': policyIds.includes(policy.id) }">
            {{ policyIds.includes(policy.id) ? '已选' : '未选' }} · {{ policy.data?.title ?? '内容已清除' }}
          </text>
          <FactLine label="政策" :value="`#${policy.id} · ${policy.data?.title ?? '内容已清除'} · v${policy.number}`" />
          <FactLine
            label="适用范围"
            :value="`${policy.data?.market} · ${labelOf(importChannels, policy.data?.channel)} · ${labelOf(languages, policy.data?.language)} · ${labelOf(importIdentities, policy.data?.data_identity)}`"
          />
          <FactLine label="主题 / 状态" :value="`${labelOf(policyTopics, policy.data?.topic)} · ${labelOf(policyStatuses, policy.availability ?? policy.status)}`" />
          <FactLine label="全文" :value="policy.data?.text" />
          <FactLine label="出处" :value="policy.data?.source" />
          <FactLine label="来源版本" :value="policy.data?.source_version" />
          <FactLine label="出处已核对" :value="policy.data?.source_confirmed" />
          <FactLine
            label="有效区间"
            :value="`${businessTimeText(policy.data?.valid_from, zone)} 至 ${policy.data?.valid_until ? businessTimeText(policy.data.valid_until, zone) : '长期'}（结束不含）`"
          />
        </view>
        <ActionButton
          label="生成本地候选回复"
          variant="primary"
          :disabled="busy || dirty || policyIds.length > 10"
          @tap="generate"
        />
        <ActionButton label="用 AI 组织客服候选" :disabled="busy || dirty" @tap="openAgent" />
        <ActionButton
          v-for="draftItem in workspace.drafts"
          :key="draftItem.id"
          :label="`消息草稿 #${draftItem.id} · ${labelOf(replyStatuses, draftItem.status)}`"
          :disabled="busy"
          @tap="inspect(draftItem.id)"
        />
      </template>

      <template v-if="draft">
        <text class="section-title">客服草稿 #{{ draft.id }} · v{{ draft.version }}</text>
        <FactLine label="处理状态 / 来源" :value="`${labelOf(replyStatuses, draft.status)} / ${labelOf(sourceLabels, draft.source_status)}`" />
        <FactLine label="生成方式 / 更新时间" :value="`${labelOf(agentLabels, draft.engine)} / ${businessTimeText(draft.updated_at, zone)}`" />
        <text class="hint">存档只记录处理状态，退款等原渠道业务仍须单独处理。系统外部未提交。</text>

        <template v-if="snapshot">
          <FactLine label="客户消息" :value="snapshot.message.body" />
          <FactLine label="消息语言 / 渠道" :value="`${labelOf(messageLanguages, snapshot.message.language)} · ${labelOf(importChannels, snapshot.message.channel)}`" />
          <FactLine label="订单关联已人工核验" :value="snapshot.order_verified" />
          <FactLine
            v-for="order in snapshot.orders"
            :key="order.source.row_id"
            label="订单 / 行 / SKU"
            :value="`${order.order_id} / ${order.line_id} / ${order.sku} · ${order.status} · ${order.fulfillment_status}`"
          />
          <FactLine label="识别诉求" :value="words(snapshot.intents)" />
          <FactLine label="人工接管原因" :value="words(snapshot.reasons)" />
          <FactLine label="交接摘要" :value="snapshot.handoff_summary" />
          <FactLine label="候选全文" :value="snapshot.reply" />
          <FactLine v-if="snapshot.model_facts && snapshot.model_facts.length > 0" label="模型引用事实" :value="words(snapshot.model_facts)" />

          <view class="field">
            <text class="field__label">回复正文（最多 6000 字）</text>
            <textarea
              class="field__input"
              :value="reply"
              :disabled="busy || manualDirty || !editable"
              @input="replyChanged(inputValue($event))"
            />
          </view>
          <text v-if="replyDirty" class="warn">正文修改后须重新审阅当前版本。</text>
          <view class="row">
            <ActionButton label="保存修改" :disabled="busy || manualDirty || !editable || !replyDirty" @tap="mutate('edit')" />
            <ActionButton v-if="dirty" label="放弃未保存修改" :disabled="busy" @tap="resetDraft" />
          </view>
          <view class="row">
            <ActionButton
              v-if="draft.status !== 'human_review'"
              label="标记需要人工"
              :disabled="busy || dirty || !editable"
              @tap="mutate('handoff')"
            />
            <ActionButton v-if="draft.status !== 'archived'" label="存档处理记录" :disabled="busy || dirty" @tap="mutate('archive')" />
            <ActionButton v-else label="重开并转人工" :disabled="busy || dirty || !live" @tap="mutate('reopen')" />
          </view>

          <text class="section-title">审阅当前版本</text>
          <FactLine
            v-if="reviewed"
            label="已审阅"
            :value="`${businessTimeText(draft.reviewed_at, zone)} · ${labelOf(languages, draft.reviewed_language)}`"
          />
          <view class="field">
            <text class="field__label">已核对目标语言</text>
            <picker mode="selector" :range="languageOptions" range-key="label" :value="languageIndex" @change="setLanguage($event)">
              <view class="field__picker">{{ languageOptions[languageIndex]?.label }}</view>
            </picker>
          </view>
          <view class="row" @tap="toggleReviewConfirmed">
            <text class="chip" :class="{ 'chip--active': reviewConfirmed }">
              {{ reviewConfirmed ? '已确认' : '未确认' }} · 已审阅回复全文、订单关联、政策有效期、目标语言与全部接管提示
            </text>
          </view>
          <ActionButton
            label="确认当前版本已审阅"
            variant="primary"
            :disabled="busy || !reviewConfirmed || language === '' || replyDirty || manualDirty || !live || reply.trim() === ''"
            @tap="mutate('review')"
          />

          <text class="section-title">外发预览与导出</text>
          <text class="hint">交付文件包含完整文案、版本和来源。每次操作前重新核对当前版本；外部状态保持未提交。</text>
          <view class="row">
            <ActionButton label="复制全文" :disabled="busy || dirty || !reviewed" @tap="deliver('copy')" />
            <ActionButton label="保存 CSV" :disabled="busy || dirty || !reviewed" @tap="deliver('save')" />
          </view>
          <text class="hint">CSV 使用服务端提供的公式防护标记；在电子表格中再次保存时请核对标记。</text>

          <text class="section-title">登记原渠道人工操作</text>
          <text class="hint">记录原渠道人工操作的自报证据；可填写证据编号或本机文件索引。此登记不等于平台回执。</text>
          <view class="field">
            <text class="field__label">操作日期</text>
            <picker mode="date" :value="occurredDay" :disabled="!canRecord" @change="occurredDay = pickerValue($event)">
              <view class="field__picker">{{ occurredDay === '' ? '未设置' : occurredDay }}</view>
            </picker>
          </view>
          <view class="field">
            <text class="field__label">操作时间</text>
            <picker mode="time" :value="occurredClock" :disabled="!canRecord" @change="occurredClock = pickerValue($event)">
              <view class="field__picker">{{ occurredClock }}</view>
            </picker>
          </view>
          <view class="field">
            <text class="field__label">操作方式（2–80 字）</text>
            <input class="field__input" :value="method" :disabled="!canRecord" @input="actionChanged(inputValue($event), 'method')" />
          </view>
          <view class="field">
            <text class="field__label">证据索引（2–500 字）</text>
            <input class="field__input" :value="evidence" :disabled="!canRecord" @input="actionChanged(inputValue($event), 'evidence')" />
          </view>
          <view class="field">
            <text class="field__label">备注（最多 1000 字）</text>
            <textarea class="field__input" :value="note" :disabled="!canRecord" @input="actionChanged(inputValue($event), 'note')" />
          </view>
          <view class="row" @tap="toggleActionConfirmed">
            <text class="chip" :class="{ 'chip--active': actionConfirmed }">
              {{ actionConfirmed ? '已确认' : '未确认' }} · 确认已在原渠道人工操作，本记录为本人自报
            </text>
          </view>
          <view class="row">
            <ActionButton
              :label="requestId === null ? '登记人工操作' : '核对并重试同次登记'"
              variant="primary"
              :disabled="busy || !reviewed || !actionConfirmed || replyDirty || reviewConfirmed"
              @tap="record"
            />
            <ActionButton label="清空未保存操作" :disabled="busy" @tap="clearManual" />
          </view>
          <ActionButton label="读取人工操作历史" :disabled="busy || dirty" @tap="readManual(false)" />
          <text v-if="manualLoaded && manual.length === 0" class="hint">暂无人工操作记录。</text>
          <view v-for="item in manual" :key="item.id" class="card">
            <text class="card__title">自报 #{{ item.id }} · 草稿 v{{ item.draft_version }}</text>
            <FactLine label="操作时间 / 登记时间" :value="`${businessTimeText(item.occurred_at, zone)} / ${businessTimeText(item.recorded_at, zone)}`" />
            <template v-if="item.details">
              <FactLine label="方式" :value="item.details.method" />
              <FactLine label="证据索引" :value="item.details.evidence_ref" />
              <FactLine label="备注" :value="item.details.note" />
            </template>
            <text v-else class="hint">相关来源已清除，证据内容已擦除。</text>
            <text class="hint">卖家自报 · 系统外部未提交</text>
          </view>
          <ActionButton v-if="manualMore" label="加载更早人工记录" :disabled="busy || dirty" @tap="readManual(true)" />
        </template>
        <text v-else class="warn">关联来源已清除，正文与证据快照已擦除。</text>
        <ActionButton label="回读当前版本与来源" :disabled="busy" @tap="load(false)" />
      </template>

      <text class="section-title">客服处理历史</text>
      <view v-if="history.length === 0 && !busy" class="card">
        <text class="hint">尚无草稿记录。</text>
      </view>
      <view v-for="item in history" :key="item.id" class="card" @tap="inspect(item.id)">
        <text class="card__title">#{{ item.id }} · {{ item.snapshot?.message?.body ?? '内容已清除' }}</text>
        <text class="hint">
          {{ labelOf(replyStatuses, item.status) }} · {{ labelOf(sourceLabels, item.source_status) }} ·
          {{ businessTimeText(item.updated_at, zone) }}
        </text>
      </view>
    </template>

    <!-- 政策与 FAQ -->
    <template v-else-if="mode === 'policies'">
      <text class="hint">按出处、市场、渠道、语言和有效期维护版本。保存新版本后重新核验已有草稿。</text>
      <view class="field">
        <text class="field__label">检索政策 / FAQ</text>
        <input class="field__input" :value="policySearch" :disabled="busy" @input="policySearch = inputValue($event)" />
      </view>
      <view class="row">
        <ActionButton label="检索" :disabled="busy" @tap="readPolicies" />
        <ActionButton label="录入政策" variant="primary" :disabled="busy" @tap="newPolicy" />
      </view>

      <template v-if="policyEditing">
        <text class="section-title">{{ policyExpected === null ? '录入新政策' : `政策 #${policyExpected} 新版本` }}</text>
        <view class="field">
          <text class="field__label">政策编号</text>
          <input class="field__input" :value="policyForm.code" :disabled="busy || policyExpected !== null" @input="setPolicyField('code', inputValue($event))" />
        </view>
        <view class="field">
          <text class="field__label">政策标题</text>
          <input class="field__input" :value="policyForm.title" :disabled="busy" @input="setPolicyField('title', inputValue($event))" />
        </view>
        <view class="field">
          <text class="field__label">主题</text>
          <picker mode="selector" :range="topicOptions" range-key="label" :value="topicIndex" @change="setPolicyChoice('topic', topicOptions, $event)">
            <view class="field__picker">{{ topicOptions[topicIndex]?.label }}</view>
          </picker>
        </view>
        <view class="field">
          <text class="field__label">市场（两位国家代码）</text>
          <input class="field__input" :value="policyForm.market" :disabled="busy" @input="setPolicyField('market', inputValue($event))" />
        </view>
        <view class="field">
          <text class="field__label">渠道</text>
          <picker mode="selector" :range="channelOptions" range-key="label" :value="policyChannelIndex" @change="setPolicyChoice('channel', channelOptions, $event)">
            <view class="field__picker">{{ channelOptions[policyChannelIndex]?.label }}</view>
          </picker>
        </view>
        <view class="field">
          <text class="field__label">语言</text>
          <picker mode="selector" :range="languageOptions" range-key="label" :value="policyLanguageIndex" @change="setPolicyChoice('language', languageOptions, $event)">
            <view class="field__picker">{{ languageOptions[policyLanguageIndex]?.label }}</view>
          </picker>
        </view>
        <view class="field">
          <text class="field__label">数据身份</text>
          <picker mode="selector" :range="identityOptions" range-key="label" :value="policyIdentityIndex" @change="setPolicyChoice('data_identity', identityOptions, $event)">
            <view class="field__picker">{{ identityOptions[policyIdentityIndex]?.label }}</view>
          </picker>
        </view>
        <view class="field">
          <text class="field__label">政策全文（最多 4000 字）</text>
          <textarea class="field__input" :value="policyForm.text" :disabled="busy" @input="setPolicyField('text', inputValue($event))" />
        </view>
        <view class="field">
          <text class="field__label">出处</text>
          <input class="field__input" :value="policyForm.source" :disabled="busy" @input="setPolicyField('source', inputValue($event))" />
        </view>
        <view class="field">
          <text class="field__label">来源版本</text>
          <input class="field__input" :value="policyForm.source_version" :disabled="busy" @input="setPolicyField('source_version', inputValue($event))" />
        </view>
        <view class="field">
          <text class="field__label">生效日期</text>
          <picker mode="date" :value="policyForm.valid_from" :disabled="busy" @change="setPolicyField('valid_from', pickerValue($event))">
            <view class="field__picker">{{ policyForm.valid_from === '' ? '未设置' : policyForm.valid_from }}</view>
          </picker>
        </view>
        <view class="field">
          <text class="field__label">生效时间</text>
          <picker mode="time" :value="policyFromClock" :disabled="busy" @change="policyFromClock = pickerValue($event)">
            <view class="field__picker">{{ policyFromClock }}</view>
          </picker>
        </view>
        <view class="field">
          <text class="field__label">结束日期（不含终点，留空长期）</text>
          <picker mode="date" :value="policyForm.valid_until" :disabled="busy" @change="setPolicyField('valid_until', pickerValue($event))">
            <view class="field__picker">{{ policyForm.valid_until === '' ? '长期' : policyForm.valid_until }}</view>
          </picker>
        </view>
        <view class="field">
          <text class="field__label">结束时间</text>
          <picker mode="time" :value="policyUntilClock" :disabled="busy" @change="policyUntilClock = pickerValue($event)">
            <view class="field__picker">{{ policyUntilClock }}</view>
          </picker>
        </view>
        <view class="row" @tap="policyConfirmed = !policyConfirmed">
          <text class="chip" :class="{ 'chip--active': policyConfirmed }">
            {{ policyConfirmed ? '已核对' : '未核对' }} · 已核对政策出处与适用范围
          </text>
        </view>
        <view class="row">
          <ActionButton label="保存政策版本" variant="primary" :disabled="busy" @tap="savePolicy" />
          <ActionButton label="放弃修改" :disabled="busy" @tap="policyEditing = false" />
        </view>
      </template>

      <view v-if="policies.length === 0 && !busy" class="card">
        <text class="hint">暂无匹配政策。</text>
      </view>
      <view v-for="policy in policies" :key="policy.id" class="card">
        <text class="card__title">{{ policy.data?.title ?? '内容已清除' }} · v{{ policy.number }}</text>
        <FactLine label="政策" :value="`#${policy.id} · ${policy.data?.title ?? '内容已清除'} · v${policy.number}`" />
        <FactLine
          label="适用范围"
          :value="`${policy.data?.market} · ${labelOf(importChannels, policy.data?.channel)} · ${labelOf(languages, policy.data?.language)} · ${labelOf(importIdentities, policy.data?.data_identity)}`"
        />
        <FactLine label="主题 / 状态" :value="`${labelOf(policyTopics, policy.data?.topic)} · ${labelOf(policyStatuses, policy.availability ?? policy.status)}`" />
        <FactLine label="全文" :value="policy.data?.text" />
        <FactLine label="出处" :value="policy.data?.source" />
        <FactLine label="来源版本" :value="policy.data?.source_version" />
        <FactLine label="出处已核对" :value="policy.data?.source_confirmed" />
        <FactLine
          label="有效区间"
          :value="`${businessTimeText(policy.data?.valid_from, zone)} 至 ${policy.data?.valid_until ? businessTimeText(policy.data.valid_until, zone) : '长期'}（结束不含）`"
        />
        <view v-if="policy.data" class="row">
          <ActionButton label="编辑新版本" :disabled="busy" @tap="editPolicy(policy)" />
          <ActionButton label="清除此政策版本" :disabled="busy" @tap="clearPolicy(policy)" />
        </view>
      </view>
      <view class="row">
        <ActionButton v-if="policyOffset > 0" label="上一页" :disabled="busy" @tap="turnPolicies(-50)" />
        <ActionButton v-if="policies.length === 50" label="下一页" :disabled="busy" @tap="turnPolicies(50)" />
      </view>
    </template>

    <!-- 手工录入消息 -->
    <template v-else>
      <text class="hint">
        手工录入会先存为待核对批次（导入 /api/shops/{shop_id}/imports，kind=messages），请到“文件导入”页面审阅字段后再提交。
      </text>
      <view class="field">
        <text class="field__label">原消息标识</text>
        <input class="field__input" :value="manualId" :disabled="busy" @input="manualId = inputValue($event)" />
      </view>
      <view class="field">
        <text class="field__label">消息日期</text>
        <picker mode="date" :value="manualDay" :disabled="busy" @change="manualDay = pickerValue($event)">
          <view class="field__picker">{{ manualDay === '' ? '未设置' : manualDay }}</view>
        </picker>
      </view>
      <view class="field">
        <text class="field__label">消息时间</text>
        <picker mode="time" :value="manualClock" :disabled="busy" @change="manualClock = pickerValue($event)">
          <view class="field__picker">{{ manualClock }}</view>
        </picker>
      </view>
      <view class="field">
        <text class="field__label">来源渠道</text>
        <picker mode="selector" :range="channelOptions" range-key="label" :value="manualChannelIndex" @change="setManualChoice('channel', $event)">
          <view class="field__picker">{{ channelOptions[manualChannelIndex]?.label }}</view>
        </picker>
      </view>
      <view class="field">
        <text class="field__label">数据身份</text>
        <picker mode="selector" :range="identityOptions" range-key="label" :value="manualIdentityIndex" @change="setManualChoice('identity', $event)">
          <view class="field__picker">{{ identityOptions[manualIdentityIndex]?.label }}</view>
        </picker>
      </view>
      <view class="field">
        <text class="field__label">消息语言</text>
        <picker mode="selector" :range="messageLanguageOptions" range-key="label" :value="manualLanguageIndex" @change="setManualChoice('language', $event)">
          <view class="field__picker">{{ messageLanguageOptions[manualLanguageIndex]?.label }}</view>
        </picker>
      </view>
      <view class="field">
        <text class="field__label">待核验订单号</text>
        <input class="field__input" :value="manualOrder" :disabled="busy" @input="manualOrder = inputValue($event)" />
      </view>
      <view class="field">
        <text class="field__label">消息原文（最多 2000 字）</text>
        <textarea class="field__input" :value="manualBody" :disabled="busy" @input="manualBody = inputValue($event)" />
      </view>
      <ActionButton label="创建待核对批次" variant="primary" block :disabled="busy" @tap="createManualMessage" />
      <ActionButton v-if="manualBatchId !== null" :label="`继续核对批次 #${manualBatchId}`" @tap="openPage('/pages/imports/index')" />
    </template>
  </PageShell>
</template>

<script setup lang="ts">
/**
 * AI 客服：草稿生成、政策、人工审阅、外发预览。
 * 接口：
 *   GET  /api/shops/{shop_id}/support/messages[/{message_id}]
 *   POST /api/shops/{shop_id}/support/messages/{message_id}/generate
 *   GET  /api/shops/{shop_id}/support/policies   POST /api/shops/{shop_id}/support/policies
 *   POST /api/shops/{shop_id}/support/policies/{policy_id}/clear
 *   GET  /api/shops/{shop_id}/support/drafts[/{draft_id}]
 *   POST /api/shops/{shop_id}/support/drafts/{draft_id}/edit
 *   POST /api/shops/{shop_id}/support/drafts/{draft_id}/action
 *   POST /api/shops/{shop_id}/support/drafts/{draft_id}/review
 *   GET  /api/shops/{shop_id}/support/drafts/{draft_id}/delivery
 *   GET/POST /api/shops/{shop_id}/support/drafts/{draft_id}/manual-actions
 *   POST /api/shops/{shop_id}/imports（手工录入消息）
 */
import { computed, ref } from 'vue'
import Taro, { useDidShow } from '@tarojs/taro'
import PageShell from '../../ui/PageShell.vue'
import FactLine from '../../ui/FactLine.vue'
import { inputValue, pickerValue } from '../../ui/forms'
import ActionButton from '../../ui/ActionButton.vue'
import { apiGet, apiPost, apiRequest, asObject, newRequestId } from '../../core/api'
import { businessTimeText, zonedIsoFromParts } from '../../core/format'
import { encodeUtf8 } from '../../core/csv'
import {
  agentLabels,
  importChannels,
  importIdentities,
  labelOf,
  languages,
  messageLanguages,
  policyStatuses,
  policyTopics,
  replyStatuses,
  sourceLabels,
} from '../../core/labels'
import { openPage, takePendingIntent, setPendingIntent, openTab } from '../../core/links'
import { ensureSession, perform, shopCurrency, shopPath, shopTimezone, state } from '../../core/store'

interface Option {
  key: string
  label: string
}

interface MessageFacts {
  id: number
  message_id: string
  body: string
  language: string
  channel: string
  sent_at: string
  order_id: string
  source: { row_id: number; data_identity: string }
}

interface OrderFact {
  order_id: string
  line_id: string
  sku: string
  status: string
  fulfillment_status: string
  source: { row_id: number }
}

interface PolicyData {
  code: string
  title: string
  topic: string
  text: string
  market: string
  channel: string
  language: string
  data_identity: string
  source: string
  source_version: string
  source_confirmed: boolean
  valid_from: string
  valid_until: string | null
}

interface Policy {
  id: number
  number: number
  status: string
  availability: string
  data: PolicyData | null
  created_at: string
}

interface ReplySnapshot {
  message: MessageFacts
  orders: OrderFact[]
  order_verified: boolean
  policies: Policy[]
  intents: string[]
  reasons: string[]
  handoff_summary: string
  reply: string
  model_facts: string[]
}

interface Reply {
  id: number
  version: number
  status: string
  source_status: string
  engine: string
  snapshot: ReplySnapshot | null
  created_at: string
  updated_at: string
  reviewed_version: number | null
  reviewed_at: string | null
  reviewed_language: string | null
}

interface SupportWorkspace {
  message: MessageFacts
  orders: OrderFact[]
  policies: Policy[]
  drafts: Reply[]
}

interface ManualAction {
  id: number
  draft_version: number
  occurred_at: string
  recorded_at: string
  details: { method: string; evidence_ref: string; note: string } | null
}

interface Delivery {
  plain_text: string
  csv_text: string
  filename: string
}

const modes = [
  { key: 'messages', label: '客服消息' },
  { key: 'policies', label: '政策与 FAQ' },
  { key: 'manual', label: '手工录入消息' },
]

const mode = ref('messages')
const search = ref('')
const messages = ref<MessageFacts[]>([])
const history = ref<Reply[]>([])
const workspace = ref<SupportWorkspace | null>(null)
const draft = ref<Reply | null>(null)
const offset = ref(0)
const reply = ref('')
const language = ref('')
const reviewConfirmed = ref(false)
const orderVerified = ref(false)
const policyIds = ref<number[]>([])
const occurredDay = ref('')
const occurredClock = ref('09:00')
const method = ref('')
const evidence = ref('')
const note = ref('')
const actionConfirmed = ref(false)
const requestId = ref<string | null>(null)
const manual = ref<ManualAction[]>([])
const manualMore = ref(false)
const manualLoaded = ref(false)
const policySearch = ref('')
const policies = ref<Policy[]>([])
const policyOffset = ref(0)
const policyEditing = ref(false)
const policyExpected = ref<number | null>(null)
const policyConfirmed = ref(false)
const policyForm = ref({ ...emptyPolicy() })
const policyFromClock = ref('00:00')
const policyUntilClock = ref('00:00')
const manualId = ref('')
const manualDay = ref('')
const manualClock = ref('09:00')
const manualChannel = ref('generic')
const manualIdentity = ref('user_import')
const manualLanguage = ref('und')
const manualOrder = ref('')
const manualBody = ref('')
const manualBatchId = ref<number | null>(null)
const busy = ref(false)
const error = ref('')
const successText = ref('')
const ready = ref(false)

const zone = computed(() => shopTimezone())
const languageOptions: Option[] = Object.entries(languages).map(([key, label]) => ({ key, label }))
const channelOptions: Option[] = Object.entries(importChannels).map(([key, label]) => ({ key, label }))
const identityOptions: Option[] = Object.entries(importIdentities).map(([key, label]) => ({ key, label }))
const policyTopicOptions: Option[] = Object.entries(policyTopics).map(([key, label]) => ({ key, label }))
const messageLanguageOptions: Option[] = Object.entries(messageLanguages).map(([key, label]) => ({ key, label }))
const topicOptions = policyTopicOptions
const languageIndex = computed(() => Math.max(0, languageOptions.findIndex((item) => item.key === language.value)))
const editable = computed(() => live.value && draft.value?.status !== 'archived')
const live = computed(() => draft.value?.source_status === 'current')
const snapshot = computed(() => draft.value?.snapshot ?? null)
const replyDirty = computed(() => draft.value !== null && reply.value !== (snapshot.value?.reply ?? ''))
const manualDirty = computed(
  () => [occurredDay.value, method.value, evidence.value, note.value].some((value) => value !== '') || actionConfirmed.value,
)
const dirty = computed(() => replyDirty.value || manualDirty.value || reviewConfirmed.value)
const reviewed = computed(
  () =>
    live.value &&
    draft.value?.reviewed_at !== null &&
    draft.value?.reviewed_at !== undefined &&
    draft.value?.reviewed_version === draft.value?.version,
)
const canRecord = computed(() => !busy.value && reviewed.value && !replyDirty.value && !reviewConfirmed.value)
const policyChannelIndex = computed(() => Math.max(0, channelOptions.findIndex((item) => item.key === policyForm.value.channel)))
const policyLanguageIndex = computed(() => Math.max(0, languageOptions.findIndex((item) => item.key === policyForm.value.language)))
const policyIdentityIndex = computed(() => Math.max(0, identityOptions.findIndex((item) => item.key === policyForm.value.data_identity)))
const topicIndex = computed(() => Math.max(0, policyTopicOptions.findIndex((item) => item.key === policyForm.value.topic)))
const manualChannelIndex = computed(() => Math.max(0, channelOptions.findIndex((item) => item.key === manualChannel.value)))
const manualIdentityIndex = computed(() => Math.max(0, identityOptions.findIndex((item) => item.key === manualIdentity.value)))
const manualLanguageIndex = computed(() => Math.max(0, messageLanguageOptions.findIndex((item) => item.key === manualLanguage.value)))

function emptyPolicy() {
  return {
    code: '',
    title: '',
    topic: 'faq',
    text: '',
    market: '',
    channel: 'generic',
    language: 'en',
    data_identity: 'user_import',
    source: '',
    source_version: '',
    valid_from: '',
    valid_until: '',
  }
}

function words(value: unknown): string {
  return Array.isArray(value) && value.length > 0 ? value.join('、') : '无'
}

function success(text: string): void {
  successText.value = text
  void Taro.showToast({ title: text, icon: 'none' })
}

useDidShow(async () => {
  if (!(await ensureSession())) return
  ready.value = true
  await load(true)
})

async function load(initial: boolean): Promise<void> {
  if (!ready.value) return
  // 挂起意图由其他页面在 switchTab 前写入，每次显示时取用一次。
  const intent = initial ? takePendingIntent('/pages/support/index') ?? {} : {}
  const message = await perform(async () => {
    await lists()
    if (initial) {
      const draftId = Number(intent.draft ?? '')
      const messageId = Number(intent.message ?? '')
      if (Number.isFinite(draftId) && draftId > 0) {
        const value = asObject<Reply>(await apiGet(shopPath(`/support/drafts/${draftId}`)))
        if (value !== null) accept(value)
      }
      if (Number.isFinite(messageId) && messageId > 0) {
        workspace.value = asObject<SupportWorkspace>(await apiGet(shopPath(`/support/messages/${messageId}`)))
      }
    } else if (draft.value !== null) {
      const value = asObject<Reply>(await apiGet(shopPath(`/support/drafts/${draft.value.id}`)))
      if (value !== null) accept(value)
    }
  })
  error.value = message
}

async function lists(): Promise<void> {
  const offsetWas = offset.value
  const [messageRows, draftRows] = await Promise.all([
    apiGet<MessageFacts[]>(shopPath('/support/messages'), { q: search.value.trim(), offset: offsetWas }),
    apiGet<Reply[]>(shopPath('/support/drafts')),
  ])
  messages.value = Array.isArray(messageRows) ? messageRows : []
  history.value = Array.isArray(draftRows) ? draftRows : []
}

async function refreshLists(): Promise<void> {
  offset.value = 0
  const message = await perform(lists)
  error.value = message
}

function turn(delta: number): void {
  offset.value = Math.max(0, offset.value + delta)
  void refreshLists()
}

function accept(value: Reply): void {
  draft.value = value
  reply.value = value.snapshot?.reply ?? ''
  const candidate = `${value.reviewed_language ?? value.snapshot?.message?.language ?? ''}`
  language.value = ['en', 'zh'].includes(candidate) ? candidate : ''
  reviewConfirmed.value = false
  orderVerified.value = false
  policyIds.value = []
  clearManual()
  manual.value = []
  manualMore.value = false
  manualLoaded.value = false
}

function replyChanged(value: string): void {
  reply.value = value
  reviewConfirmed.value = false
}

function actionChanged(value: string, field: 'method' | 'evidence' | 'note'): void {
  if (field === 'method') method.value = value
  if (field === 'evidence') evidence.value = value
  if (field === 'note') note.value = value
  actionConfirmed.value = false
  requestId.value = null
}

function clearManual(): void {
  occurredDay.value = ''
  occurredClock.value = '09:00'
  method.value = ''
  evidence.value = ''
  note.value = ''
  actionConfirmed.value = false
  requestId.value = null
}

function resetDraft(): void {
  if (draft.value !== null) accept(draft.value)
}

function toggleOrderVerified(): void {
  if (busy.value || (workspace.value?.orders.length ?? 0) === 0) return
  orderVerified.value = !orderVerified.value
}

function togglePolicy(id: number): void {
  if (busy.value) return
  if (policyIds.value.includes(id)) {
    policyIds.value = policyIds.value.filter((item) => item !== id)
  } else if (policyIds.value.length < 10) {
    policyIds.value = [...policyIds.value, id]
  } else {
    error.value = '最多选择 10 份政策。'
  }
}

function toggleReviewConfirmed(): void {
  if (busy.value || replyDirty.value || manualDirty.value || !live.value) return
  reviewConfirmed.value = !reviewConfirmed.value
}

function toggleActionConfirmed(): void {
  if (!canRecord.value) return
  actionConfirmed.value = !actionConfirmed.value
}

function setLanguage(event: { detail: { value: string } }): void {
  if (busy.value || replyDirty.value || manualDirty.value || !live.value) return
  language.value = languageOptions[Number(event.detail.value)]?.key ?? ''
  reviewConfirmed.value = false
}

async function choose(id: number): Promise<void> {
  const message = await perform(async () => {
    workspace.value = asObject<SupportWorkspace>(await apiGet(shopPath(`/support/messages/${id}`)))
    draft.value = null
    orderVerified.value = false
    policyIds.value = []
    clearManual()
    reviewConfirmed.value = false
  })
  error.value = message
}

async function inspect(id: number): Promise<void> {
  const message = await perform(async () => {
    workspace.value = null
    const value = asObject<Reply>(await apiGet(shopPath(`/support/drafts/${id}`)))
    if (value !== null) accept(value)
  })
  error.value = message
}

async function generate(): Promise<void> {
  const current = workspace.value
  if (current === null) return
  if (policyIds.value.length > 10) {
    error.value = '最多选择 10 份政策。'
    return
  }
  const message = await perform(async () => {
    const value = asObject<Reply>(
      await apiPost(shopPath(`/support/messages/${current.message.id}/generate`), {
        expected_source_row_id: current.message.source.row_id,
        expected_order_row_ids: orderVerified.value ? current.orders.map((order) => order.source.row_id) : [],
        order_verified: orderVerified.value,
        policy_ids: policyIds.value,
      }),
    )
    if (value !== null) accept(value)
    await lists()
  })
  if (message === '') success('候选回复与接管摘要已保存，请核对全部诉求和依据。')
  else error.value = message
}

async function mutate(action: 'edit' | 'review' | 'handoff' | 'archive' | 'reopen'): Promise<void> {
  const current = draft.value
  if (current === null) return
  const message = await perform(async () => {
    let value: Reply | null
    if (action === 'edit') {
      if (reply.value.trim() === '' || reply.value.length > 6000) {
        throw new Error('回复须为 1–6000 字。')
      }
      value = asObject<Reply>(
        await apiPost(shopPath(`/support/drafts/${current.id}/edit`), {
          expected_version: current.version,
          reply: reply.value,
        }),
      )
    } else if (action === 'review') {
      if (!reviewConfirmed.value || replyDirty.value || manualDirty.value || language.value === '') {
        throw new Error('请核对全文和目标语言。')
      }
      value = asObject<Reply>(
        await apiPost(shopPath(`/support/drafts/${current.id}/review`), {
          expected_version: current.version,
          target_language: language.value,
          confirmed: true,
        }),
      )
    } else {
      if (dirty.value) throw new Error('请先保存或放弃未完成修改。')
      value = asObject<Reply>(
        await apiPost(shopPath(`/support/drafts/${current.id}/action`), {
          expected_version: current.version,
          action,
        }),
      )
    }
    if (value !== null) accept(value)
    await lists()
  })
  if (message === '') success('当前版本处理结果已保存。')
  else error.value = message
}

async function deliver(action: 'copy' | 'save'): Promise<void> {
  const current = draft.value
  if (current === null || busy.value || dirty.value || !reviewed.value) return
  const message = await perform(async () => {
    const artifact = asObject<Delivery>(
      await apiGet(shopPath(`/support/drafts/${current.id}/delivery`), {
        expected_version: current.version,
      }),
    )
    if (artifact === null) throw new Error('交付内容无法读取，请刷新后重试。')
    if (action === 'copy') {
      await Taro.setClipboardData({ data: artifact.plain_text })
      success('完整文案、版本与来源已复制，请在原渠道核对后使用。')
      return
    }
    const path = `${Taro.env.USER_DATA_PATH}/${artifact.filename}`
    Taro.getFileSystemManager().writeFileSync(path, artifact.csv_text, 'utf8')
    const saver = (Taro as unknown as { saveFileToDisk?: (options: { filePath: string }) => Promise<unknown> })
      .saveFileToDisk
    if (typeof saver === 'function') {
      await saver({ filePath: path })
      success('通用 CSV 已保存。')
      return
    }
    await Taro.setClipboardData({ data: artifact.csv_text })
    success('当前客户端不支持直接保存文件，已把 CSV 文本复制到剪贴板，并写入小程序本地文件。')
  })
  error.value = message
}

async function readManual(more: boolean): Promise<void> {
  const current = draft.value
  if (current === null) return
  const message = await perform(async () => {
    const query: Record<string, number> = {}
    if (more && manual.value.length > 0) query.before = manual.value[manual.value.length - 1].id
    const rows = await apiGet<ManualAction[]>(shopPath(`/support/drafts/${current.id}/manual-actions`), query)
    const incoming = Array.isArray(rows) ? rows : []
    manual.value = more ? [...manual.value, ...incoming] : incoming
    manualMore.value = incoming.length === 50
    manualLoaded.value = true
  })
  error.value = message
}

async function record(): Promise<void> {
  const current = draft.value
  if (current === null) return
  const message = await perform(async () => {
    if (!reviewed.value || replyDirty.value || reviewConfirmed.value || !actionConfirmed.value) {
      throw new Error('请先审阅版本并确认人工操作。')
    }
    if (
      method.value.trim().length < 2 || method.value.length > 80 ||
      evidence.value.trim().length < 2 || evidence.value.length > 500 ||
      note.value.length > 1000
    ) {
      throw new Error('方式须为 2–80 字，证据索引 2–500 字，备注最多 1000 字。')
    }
    const occurred = zonedIsoFromParts(occurredDay.value, occurredClock.value, zone.value)
    if (occurred === null) throw new Error('请选择有效的人工操作日期与时间。')
    if (requestId.value === null) requestId.value = newRequestId()
    await apiPost(shopPath(`/support/drafts/${current.id}/manual-actions`), {
      request_id: requestId.value,
      expected_version: current.version,
      occurred_at: occurred,
      method: method.value.trim(),
      evidence_ref: evidence.value.trim(),
      note: note.value.trim(),
      confirmed: true,
    })
    clearManual()
    const rows = await apiGet<ManualAction[]>(shopPath(`/support/drafts/${current.id}/manual-actions`))
    manual.value = Array.isArray(rows) ? rows : []
    manualLoaded.value = true
  })
  if (message === '') success('人工操作自报已登记。此记录不等于平台回执，系统外部状态仍为未提交。')
  else error.value = message
}

function openAgent(): void {
  const current = workspace.value
  if (current === null) return
  setPendingIntent('/pages/agent/index', {
    mode: 'support_model',
    message: `${current.message.id}`,
    identity: current.message.source.data_identity,
    channel: current.message.channel,
  })
  openTab('/pages/agent/index')
}

function openImports(): void {
  openPage('/pages/imports/index', { kind: 'messages' })
}

/* ---------- 政策与 FAQ ---------- */

async function readPolicies(): Promise<void> {
  const message = await perform(async () => {
    const rows = await apiGet<Policy[]>(shopPath('/support/policies'), {
      q: policySearch.value.trim(),
      offset: policyOffset.value,
    })
    policies.value = Array.isArray(rows) ? rows : []
  })
  error.value = message
}

function turnPolicies(delta: number): void {
  policyOffset.value = Math.max(0, policyOffset.value + delta)
  void readPolicies()
}

function newPolicy(): void {
  policyExpected.value = null
  policyForm.value = { ...emptyPolicy(), market: currentMarket(), channel: 'generic', language: 'en', data_identity: 'user_import' }
  policyFromClock.value = '00:00'
  policyUntilClock.value = '00:00'
  policyConfirmed.value = false
  policyEditing.value = true
}

function editPolicy(policy: Policy): void {
  const data = policy.data
  if (data === null) return
  policyExpected.value = policy.id
  policyForm.value = {
    code: data.code,
    title: data.title,
    topic: data.topic,
    text: data.text,
    market: data.market,
    channel: data.channel,
    language: data.language,
    data_identity: data.data_identity,
    source: data.source,
    source_version: data.source_version,
    valid_from: data.valid_from.slice(0, 10),
    valid_until: data.valid_until === null ? '' : data.valid_until.slice(0, 10),
  }
  policyFromClock.value = '00:00'
  policyUntilClock.value = '00:00'
  policyConfirmed.value = false
  policyEditing.value = true
}

function setPolicyField(field: 'code' | 'title' | 'text' | 'market' | 'source' | 'source_version' | 'valid_from' | 'valid_until', value: string): void {
  policyForm.value = { ...policyForm.value, [field]: value }
  policyConfirmed.value = false
}

function setPolicyChoice(field: 'topic' | 'channel' | 'language' | 'data_identity', options: Option[], event: { detail: { value: string } }): void {
  policyForm.value = { ...policyForm.value, [field]: options[Number(event.detail.value)]?.key ?? '' }
  policyConfirmed.value = false
}

function currentMarket(): string {
  const shop = state.shops.find((item) => item.id === state.shopId)
  return `${shop?.market ?? ''}`
}

async function savePolicy(): Promise<void> {
  const form = policyForm.value
  const message = await perform(async () => {
    const limits: Array<[string, number]> = [['code', 80], ['title', 120], ['text', 4000], ['source', 400], ['source_version', 80]]
    for (const [key, limit] of limits) {
      const value = `${(form as unknown as Record<string, string>)[key] ?? ''}`.trim()
      if (value === '') throw new Error(`请填写${key}。`)
      if (value.length > limit) throw new Error(`${key} 最多 ${limit} 字。`)
    }
    const market = form.market.trim().toUpperCase()
    if (!/^[A-Z]{2}$/.test(market)) throw new Error('市场须为两位国家代码。')
    const validFrom = zonedIsoFromParts(form.valid_from, policyFromClock.value, zone.value)
    if (validFrom === null) throw new Error('请选择有效的生效日期与时间。')
    let validUntil: string | null = null
    if (form.valid_until !== '') {
      validUntil = zonedIsoFromParts(form.valid_until, policyUntilClock.value, zone.value)
      if (validUntil === null) throw new Error('请选择有效的结束日期与时间。')
      if (Date.parse(validUntil) <= Date.parse(validFrom)) {
        throw new Error('政策结束时间须晚于生效时间（结束时间不包含在有效区间）。')
      }
    }
    await apiPost(shopPath('/support/policies'), {
      expected_policy_id: policyExpected.value,
      data: {
        code: form.code.trim(),
        title: form.title.trim(),
        topic: form.topic,
        text: form.text.trim(),
        market,
        channel: form.channel,
        language: form.language,
        data_identity: form.data_identity,
        source: form.source.trim(),
        source_version: form.source_version.trim(),
        source_confirmed: policyConfirmed.value,
        valid_from: validFrom,
        valid_until: validUntil,
      },
    })
    policyEditing.value = false
    await readPolicies()
  })
  if (message === '') success('政策新版本已保存，已有草稿需重新核对政策。')
  else error.value = message
}

async function clearPolicy(policy: Policy): Promise<void> {
  const modal = await Taro.showModal({
    title: `清除政策 #${policy.id}`,
    content: '此政策版本及引用它的客服草稿正文将被擦除，保留编号与状态记录。',
    confirmText: '确认',
    cancelText: '返回',
  })
  if (!modal.confirm) return
  const message = await perform(async () => {
    await apiPost(shopPath(`/support/policies/${policy.id}/clear`), {})
    await readPolicies()
  })
  if (message === '') success('政策版本与依赖正文已清除。')
  else error.value = message
}

/* ---------- 手工录入消息 ---------- */

function setManualChoice(field: 'channel' | 'identity' | 'language', event: { detail: { value: string } }): void {
  const options =
    field === 'channel' ? channelOptions : field === 'identity' ? identityOptions : messageLanguageOptions
  const value = options[Number(event.detail.value)]?.key ?? ''
  if (field === 'channel') manualChannel.value = value
  if (field === 'identity') manualIdentity.value = value
  if (field === 'language') manualLanguage.value = value
}

async function createManualMessage(): Promise<void> {
  const message = await perform(async () => {
    if (manualId.value.length > 120 || manualOrder.value.length > 120 || manualBody.value.length > 2000) {
      throw new Error('消息/订单标识最多 120 字，原文最多 2000 字。')
    }
    if (manualId.value.trim() === '' || manualBody.value.trim() === '') {
      throw new Error('请填写原消息标识与消息原文。')
    }
    const sent = zonedIsoFromParts(manualDay.value, manualClock.value, zone.value)
    if (sent === null) throw new Error('请选择有效的消息日期与时间。')
    const escape = (value: string): string => `"${value.replace(/"/g, '""')}"`
    const csv = `message_id,sent_at,body,language,order_id\n${[manualId.value, sent, manualBody.value, manualLanguage.value, manualOrder.value].map(escape).join(',')}\n`
    const created = asObject<{ id: number }>(
      await apiRequest(shopPath('/imports'), {
        method: 'POST',
        query: {
          kind: 'messages',
          source_channel: manualChannel.value,
          data_identity: manualIdentity.value,
          timezone: zone.value,
          filename: 'manual-message.csv',
        },
        bytes: toArrayBuffer(encodeUtf8(csv)),
        contentType: 'application/octet-stream',
      }),
    )
    if (created === null) throw new Error('手工消息未返回批次号，请到文件导入页核对。')
    manualBatchId.value = created.id
  })
  if (message === '') success('消息已存为待核对批次。请在导入页审阅字段、旧值与新值，再提交。')
  else error.value = message
}

function toArrayBuffer(bytes: Uint8Array): ArrayBuffer {
  const copy = new ArrayBuffer(bytes.length)
  new Uint8Array(copy).set(bytes)
  return copy
}
</script>
