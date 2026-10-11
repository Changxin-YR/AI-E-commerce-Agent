import 'package:flutter_test/flutter_test.dart';
import 'package:soloops_flutter/features/agent/agent_page.dart';

void main() {
  final generic = <String, dynamic>{
    'source': {'data_identity': 'synthetic'},
    'source_channel': 'generic',
  };
  final amazon = {...generic, 'source_channel': 'amazon'};
  final legacy = <String, dynamic>{
    'source': {'data_identity': 'synthetic'}
  };
  test('B1 only offers products with proven matching source scope', () {
    bool eligible(Map<String, dynamic> p) => agentProductMatchesScope(p,
        template: 'margin_review', identity: 'synthetic', channel: 'amazon');
    expect([generic, amazon, legacy].where(eligible), [amazon]);
    expect(
        agentProductMatchesScope(amazon,
            template: 'margin_review',
            identity: 'user_import',
            channel: 'amazon'),
        isFalse);
  });
  test('Listing workflows retain identity-only product selection', () {
    for (final template in ['listing', 'listing_model', 'natural']) {
      expect(
          agentProductMatchesScope(generic,
              template: template, identity: 'synthetic', channel: 'amazon'),
          isTrue);
      expect(
          agentProductMatchesScope(legacy,
              template: template, identity: 'synthetic', channel: 'amazon'),
          isTrue);
    }
  });
}
