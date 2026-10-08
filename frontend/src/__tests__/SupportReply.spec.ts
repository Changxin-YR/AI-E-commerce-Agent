import { mount } from '@vue/test-utils'
import { expect, it } from 'vitest'
import SupportReply from '@/components/SupportReply.vue'
import type { ReplyDraft } from '@/types/support'

function draft(): ReplyDraft {
  return {
    id: 1,
    version: 1,
    status: 'human_review',
    source_status: 'current',
    engine: 'local_rules',
    created_at: '2026-10-09T01:00:00Z',
    updated_at: '2026-10-09T01:00:00Z',
    external_status: 'not_submitted',
    snapshot: {
      message: {
        id: 1,
        message_id: 'M1',
        body: '<script>alert(1)</script>',
        language: 'en',
        channel: 'generic',
        sent_at: '2026-10-09T01:00:00Z',
        order_id: '',
        source: {
          batch_id: 1,
          row_id: 1,
          row_number: 2,
          filename: 'synthetic.csv',
          sheet_name: '',
          imported_at: '2026-10-09T01:00:00Z',
          exported_at: null,
          data_identity: 'synthetic',
        },
      },
      orders: [],
      order_verified: false,
      policies: [],
      intents: ['shipping', 'refund'],
      reasons: ['未知物流'],
      handoff_summary: '待人工核验',
      reply: 'Needs verification.',
    },
  }
}
it('keeps unsaved text from being archived and removes source content on purge', async () => {
  const wrapper = mount(SupportReply, {
    props: { item: draft(), shopId: 1, busy: false, timezone: 'Asia/Shanghai' },
  })
  const archive = () => wrapper.findAll('button').find((b) => b.text() === '存档处理记录')!
  await wrapper.get('textarea').setValue('Manually edited')
  expect(archive().attributes('disabled')).toBeDefined()
  expect(wrapper.find('script').exists()).toBe(false)
  await wrapper.get('form').trigger('submit')
  expect(wrapper.emitted('edit')).toEqual([['Manually edited']])
  await wrapper.setProps({
    item: { ...draft(), version: 2, source_status: 'cleared', snapshot: null },
  })
  expect(wrapper.find('textarea').exists()).toBe(false)
  expect(wrapper.text()).not.toContain('alert(1)')
  expect(wrapper.text()).toContain('正文和证据快照已擦除')
})
