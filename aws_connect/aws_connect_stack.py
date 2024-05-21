import os
from aws_cdk import (
    Stack,
    aws_iam as _iam,
    aws_connect as connect,
    aws_lex as lex,
    Aws,
    RemovalPolicy,
    CfnOutput
)
from constructs import Construct

class AwsConnectStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # create connect instance 
        connect_attributes = connect.CfnInstance.AttributesProperty(
            inbound_calls=True,
            outbound_calls=True,
            auto_resolve_best_voices=True,
            contactflow_logs=True,
            contact_lens=False,
            early_media=True,
            use_custom_tts_voices=False
        )
        
        # create connect instance
        self.connect_instance = connect.CfnInstance(self, "connect_instance",
            attributes=connect_attributes,
            identity_management_type="CONNECT_MANAGED",
            instance_alias="HelpDesk4084",
        )
        self.connect_instance.apply_removal_policy(RemovalPolicy.DESTROY)

        # create connect phone number
        phone_number = connect.CfnPhoneNumber(self, "phone_number",
            target_arn=self.connect_instance.attr_arn,
            # uncomment line below to use a specific area code
            # prefix="+678",
            description="HelpDesk Phone Number",
            country_code="US",
            type="DID"                                      
        )
        
        # create lex sample utterances
        self.pass1_utterance = lex.CfnBot.SampleUtteranceProperty(
            utterance="I forgot my password")
        self.pass2_utterance = lex.CfnBot.SampleUtteranceProperty(
            utterance="reset my password")
        self.network1_utterance = lex.CfnBot.SampleUtteranceProperty(
            utterance="I can't access the internet")
        self.network2_utterance = lex.CfnBot.SampleUtteranceProperty(
            utterance="my email is down")

        # create lex intent
        self.password_intent = lex.CfnBot.IntentProperty(
            name="PasswordReset",
            description="Test intent for password",
            sample_utterances=[self.pass1_utterance, self.pass2_utterance],        
        )
        self.network_intent = lex.CfnBot.IntentProperty(
            name="NetworkIssue",
            description="Test intent for internet connecton",
            sample_utterances=[self.network1_utterance, self.network2_utterance],        
        )
        self.fallback_intent = lex.CfnBot.IntentProperty(
            name="FallbackIntent",
            description="Default intent when no other intent matches",
            parent_intent_signature="AMAZON.FallbackIntent",
        )

        # # Create lex bot locale property
        self.bot_locale_property = lex.CfnBot.BotLocaleProperty(
            locale_id="en_US",
            nlu_confidence_threshold=0.4,
            voice_settings=lex.CfnBot.VoiceSettingsProperty(
                voice_id="Joanna",        
            ),
            intents=[self.password_intent, self.network_intent, self.fallback_intent]               
        )
        
        # create lex bot service role
        self.lex_role = _iam.Role(self, "lex_role",
            assumed_by=_iam.ServicePrincipal("connect.amazonaws.com"),                        
        )
        
        # Create lex bot
        self.lex_bot = lex.CfnBot(self, "lex_bot",
            data_privacy={
                "ChildDirected": False
            },
            idle_session_ttl_in_seconds=1800,
            name="HelpDeskBot",
            role_arn=self.lex_role.role_arn,
            auto_build_bot_locales=True,
            bot_locales=[self.bot_locale_property]
        )
        self.lex_bot.apply_removal_policy(RemovalPolicy.DESTROY)
        self.lex_bot.node.add_dependency(self.lex_role)

        # create lex bot version
        cfn_bot_version = lex.CfnBotVersion(self, "MyCfnBotVersion",
            bot_id=self.lex_bot.attr_id,
            description="Production Version",
            bot_version_locale_specification=[lex.CfnBotVersion.BotVersionLocaleSpecificationProperty(
               bot_version_locale_details=lex.CfnBotVersion.BotVersionLocaleDetailsProperty(
               source_bot_version="DRAFT"
            ),
            locale_id=self.bot_locale_property.locale_id
          )],           
        )
       
        # create lex bot alias
        self.lex_bot_alias = lex.CfnBotAlias(self, "lex_bot_alias",
            bot_id=self.lex_bot.attr_id,
            bot_alias_name="Prod",
            description="HelpDesk bot alias",
            bot_version=cfn_bot_version.attr_bot_version
        )

        # integrate bot with connect instance
        self.integration = connect.CfnIntegrationAssociation(self, "integration",
            instance_id=f"arn:aws:connect:{Aws.REGION}:{Aws.ACCOUNT_ID}:instance/{self.connect_instance.attr_id}",
            integration_type="LEX_BOT",
            integration_arn=f"arn:aws:lex:{Aws.REGION}:{Aws.ACCOUNT_ID}:bot-alias/{self.lex_bot.attr_id}/{self.lex_bot_alias.attr_bot_alias_id}",
        )
        self.integration.node.add_dependency(self.connect_instance)

        # create hours of operation for connect
        end_time = connect.CfnHoursOfOperation.HoursOfOperationTimeSliceProperty(
            hours=23,
            minutes=59
        )
        start_time = connect.CfnHoursOfOperation.HoursOfOperationTimeSliceProperty(
            hours=8,
            minutes=0
        )
        cfn_hours_of_operation = connect.CfnHoursOfOperation(self, "MyCfnHoursOfOperation",
            config=[connect.CfnHoursOfOperation.HoursOfOperationConfigProperty(
                        day="MONDAY",
                        end_time=end_time,
                        start_time=start_time    
                    ),
                    connect.CfnHoursOfOperation.HoursOfOperationConfigProperty(
                        day="TUESDAY",
                        end_time=end_time,
                        start_time=start_time    
                    ),
                    connect.CfnHoursOfOperation.HoursOfOperationConfigProperty(
                        day="WEDNESDAY",
                        end_time=end_time,
                        start_time=start_time    
                    ),
                    connect.CfnHoursOfOperation.HoursOfOperationConfigProperty(
                        day="THURSDAY",
                        end_time=end_time,
                        start_time=start_time    
                    ),
                    connect.CfnHoursOfOperation.HoursOfOperationConfigProperty(                       
                        day="FRIDAY",
                        end_time=end_time,
                        start_time=start_time    
                    )                                                        
                ],
            instance_arn=self.connect_instance.attr_arn,
            name="HelpDesk Hours",
            time_zone="EST5EDT",
            description="Password and Internet issues",
        )

        # create connect password queue
        self.password_queue = connect.CfnQueue(self, "password_queue",
            hours_of_operation_arn=cfn_hours_of_operation.attr_hours_of_operation_arn,
            instance_arn=self.connect_instance.attr_arn,
            name="PasswordReset",
            description="Help customers reset their password",
            max_contacts=10,
            outbound_caller_config=connect.CfnQueue.OutboundCallerConfigProperty(
                outbound_caller_id_name="Henry Corp",
                outbound_caller_id_number_arn=phone_number.attr_phone_number_arn
            ),
        )

        # create connect network queue
        self.network_queue = connect.CfnQueue(self, "network_queue",
            hours_of_operation_arn=cfn_hours_of_operation.attr_hours_of_operation_arn,
            instance_arn=self.connect_instance.attr_arn,
            name="NetworkIssue",
            description="Help customers with their network issues",
            max_contacts=10,
            outbound_caller_config=connect.CfnQueue.OutboundCallerConfigProperty(
                outbound_caller_id_name="Henry Corp",
                outbound_caller_id_number_arn=phone_number.attr_phone_number_arn
            ),
        )

        # create connect outbound queue
        self.outbound_queue = connect.CfnQueue(self, "outbound_queue",
            hours_of_operation_arn=cfn_hours_of_operation.attr_hours_of_operation_arn,
            instance_arn=self.connect_instance.attr_arn,
            name="OutBoundQueue",
            description="Default Outbound Queue",
            max_contacts=10,
        )

        # create connect routing profile
        self.routing_profile = connect.CfnRoutingProfile(self, "routing_profile",
            default_outbound_queue_arn=self.outbound_queue.attr_queue_arn,
            instance_arn=self.connect_instance.attr_arn,
            name="HelpDeskRoutingProfile",
            media_concurrencies=[
                connect.CfnRoutingProfile.MediaConcurrencyProperty(channel="VOICE", concurrency=1),
                connect.CfnRoutingProfile.MediaConcurrencyProperty(channel="CHAT", concurrency=1)
            ],
            description="Routing profile for Help Desk",
            queue_configs=[
                connect.CfnRoutingProfile.RoutingProfileQueueConfigProperty(
                delay=0,
                priority=1,
                queue_reference=connect.CfnRoutingProfile.RoutingProfileQueueReferenceProperty(
                channel="VOICE", 
                queue_arn=self.password_queue.attr_queue_arn)
                ),
                connect.CfnRoutingProfile.RoutingProfileQueueConfigProperty(
                delay=0, 
                priority=1,
                queue_reference=connect.CfnRoutingProfile.RoutingProfileQueueReferenceProperty(
                channel="CHAT",
                queue_arn=self.password_queue.attr_queue_arn)
                ),
                connect.CfnRoutingProfile.RoutingProfileQueueConfigProperty(
                delay=0,
                priority=1,
                queue_reference=connect.CfnRoutingProfile.RoutingProfileQueueReferenceProperty(
                channel="VOICE",
                queue_arn=self.network_queue.attr_queue_arn)
                ),
                connect.CfnRoutingProfile.RoutingProfileQueueConfigProperty(
                delay=0,
                priority=1,
                queue_reference=connect.CfnRoutingProfile.RoutingProfileQueueReferenceProperty(
                channel="CHAT",
                queue_arn=self.network_queue.attr_queue_arn)
                ),

                connect.CfnRoutingProfile.RoutingProfileQueueConfigProperty(
                delay=0,
                priority=1,
                queue_reference=connect.CfnRoutingProfile.RoutingProfileQueueReferenceProperty(
                channel="VOICE",
                queue_arn=self.outbound_queue.attr_queue_arn)
                ),
                connect.CfnRoutingProfile.RoutingProfileQueueConfigProperty(
                delay=0,
                priority=1,
                queue_reference=connect.CfnRoutingProfile.RoutingProfileQueueReferenceProperty(
                channel="CHAT",
                queue_arn=self.outbound_queue.attr_queue_arn)
                ),
                connect.CfnRoutingProfile.RoutingProfileQueueConfigProperty(
                delay=0,
                priority=1,
                queue_reference=connect.CfnRoutingProfile.RoutingProfileQueueReferenceProperty(
                channel="TASK",
                queue_arn=self.outbound_queue.attr_queue_arn)
                )

            ]
        )

        # convert json file to string      
        with open("./configs/contact-flow-content.json", "r") as read_content:
            content = read_content.read()
            content = content.replace("botaliasarn", str(self.lex_bot_alias.attr_arn))
            content = content.replace("passwordqueuearn", str(self.password_queue.attr_queue_arn))
            content = content.replace("networkqueuearn", str(self.network_queue.attr_queue_arn))

        # create connect contact flow
        self.contact_flow = connect.CfnContactFlow(self, "contact_flow",
            content=content,
            instance_arn=self.connect_instance.attr_arn,
            name="Help Desk",
            type="CONTACT_FLOW",
            description="Default flow for HelpDesk"
        )

        # create connect security profile
        self.security_profile = connect.CfnSecurityProfile(self, "security_profile",
            description="Admin security profile for HelpDesk",
            instance_arn=self.connect_instance.attr_arn,
            security_profile_name="HelpDeskAdmin",
            permissions=[
                "AccessMetrics", "AccessMetrics.AgentActivityAudit.Access", "AccessMetrics.Dashboards.Access", "AccessMetrics.HistoricalMetrics.Access", "AccessMetrics.RealTimeMetrics.Access", 
                "AgentGrouping.Create", "AgentGrouping.Edit", "AgentGrouping.EnableAndDisable", "AgentGrouping.View", 
                "AgentStates.Create", "AgentStates.Edit", "AgentStates.EnableAndDisable", "AgentStates.View", 
                "AgentTimeCard.View",
                "Audio.View", 
                "AudioDeviceSettings.Access", 
                "BasicAgentAccess", 
                "Campaigns.Create", "Campaigns.Delete", "Campaigns.Edit", "Campaigns.Manage", "Campaigns.View", 
                "Capacity.Edit", "Capacity.Publish", "Capacity.View",
                "CaseFields.Create", "CaseFields.Edit", "CaseFields.View", "CaseHistory.View", 
                "CaseTemplates.Create", "CaseTemplates.Edit", "CaseTemplates.View", 
                "Cases.Create", "Cases.Edit", "Cases.View", 
                "ChatTestMode",
                "ConfigureContactAttributes.View", "ContactAttributes.View", 
                "ContactFlowModules.Create", "ContactFlowModules.Delete", "ContactFlowModules.Edit", "ContactFlowModules.Publish", "ContactFlowModules.View", 
                "ContactFlows.Create", "ContactFlows.Delete", "ContactFlows.Edit", "ContactFlows.Publish", "ContactFlows.View", 
                "ContactLensCustomVocabulary.Edit", "ContactLensCustomVocabulary.View", "ContactLensPostContactSummary.View", 
                "ContactRecording.Access", "ContactSearch.View",
                "ContactSearchQuickViewWidget.Create", "ContactSearchQuickViewWidget.Delete", "ContactSearchQuickViewWidget.Edit", "ContactSearchQuickViewWidget.View", 
                "ContactSearchWithCharacteristics.Access", "ContactSearchWithCharacteristics.View",
                "ContactSearchWithKeywords.Access", "ContactSearchWithKeywords.View", 
                "ContentManagement.Create", "ContentManagement.Delete", "ContentManagement.Edit", "ContentManagement.View", 
                "CustomViews.Access", 
                "CustomerProfiles.CalculatedAttributes.Create","CustomerProfiles.CalculatedAttributes.Delete", "CustomerProfiles.CalculatedAttributes.Edit", "CustomerProfiles.CalculatedAttributes.View",
                "CustomerProfiles.Create", "CustomerProfiles.Edit", "CustomerProfiles.View", 
                "DeleteCallRecordings", "DownloadCallRecordings",
                "Evaluation.Create", "Evaluation.Delete", "Evaluation.Edit", "Evaluation.View", 
                "EvaluationAssistant.Access", 
                "EvaluationForms.Create", "EvaluationForms.Delete", "EvaluationForms.Edit", "EvaluationForms.View", 
                "ForecastScheduleInterval.Edit", "ForecastScheduleInterval.View", "Forecasting.Edit", "Forecasting.Publish", "Forecasting.View", 
                "GraphTrends.View", 
                "HistoricalChanges.View", 
                "HoursOfOperation.Create", "HoursOfOperation.Delete", "HoursOfOperation.Edit", "HoursOfOperation.View", 
                "ListenCallRecordings", 
                "ManagerBargeIn", "ManagerListenIn",
                "MetricsReports.Create", "MetricsReports.Delete", "MetricsReports.Edit", "MetricsReports.Publish", "MetricsReports.Schedule", "MetricsReports.Share", "MetricsReports.View", 
                "MyContacts.View", 
                "OutboundCallAccess", 
                "PhoneNumbers.Claim", "PhoneNumbers.Edit", "PhoneNumbers.Release", "PhoneNumbers.View",
                "PredefinedAttributes.Create", "PredefinedAttributes.Delete", "PredefinedAttributes.Edit", "PredefinedAttributes.View",
                "Prompts.Create", "Prompts.Delete", "Prompts.Edit", "Prompts.View",
                "Queues.Create", "Queues.Edit", "Queues.EnableAndDisable", "Queues.Purge", "Queues.View",
                "RealtimeContactLens.View", 
                "RedactedData.View",
                "ReportSchedules.Create", "ReportSchedules.Delete", "ReportSchedules.Edit", "ReportSchedules.View",
                "ReportsAdmin.Access", "ReportsAdmin.Delete", "ReportsAdmin.Publish", "ReportsAdmin.Schedule", "ReportsAdmin.View",
                "RoutingPolicies.Create", "RoutingPolicies.Edit", "RoutingPolicies.View",
                "Rules.Create", "Rules.Delete", "Rules.Edit", "Rules.View",
                "Scheduling.Edit", "Scheduling.Publish", "Scheduling.View",
                "ScreenRecording.Access", "ScreenRecording.Delete", "ScreenRecording.Download",
                "SecurityProfiles.Create", "SecurityProfiles.Delete", "SecurityProfiles.Edit", "SecurityProfiles.View",
                "StaffCalendar.Edit", "StaffCalendar.View",
                "StopContact.Enabled",
                "TaskTemplates.Create", "TaskTemplates.Delete", "TaskTemplates.Edit", "TaskTemplates.View",
                "TeamCalendar.Edit", "TeamCalendar.View",
                "TimeOff.Approve", "TimeOff.Edit", "TimeOff.View", "TimeOffBalance.Edit", "TimeOffBalance.View",
                "Transcript.View",
                "TransferContact.Enabled",
                "TransferDestinations.Create", "TransferDestinations.Delete", "TransferDestinations.Edit", "TransferDestinations.View",
                "UnredactedData.View",
                "UpdateContactSchedule.Enabled",
                "Users.Create", "Users.Delete", "Users.Edit", "Users.EditPermission", "Users.EnableAndDisable", "Users.View",
                "VideoContact.Access",
                "Views.Create", "Views.Edit", "Views.Remove", "Views.View",
                "VoiceId.Access",
                "VoiceIdAttributesAndSearch.View",
                "VoiceIdUpdateSpeakerId.Access",
                "Wisdom.View"
            ]           
        )

        # create connect user with Admin rights
        self.connect_user = connect.CfnUser(self, "connect_user",
            instance_arn=self.connect_instance.attr_arn,
            phone_config=connect.CfnUser.UserPhoneConfigProperty(
                phone_type="SOFT_PHONE",
                auto_accept=False,
                after_contact_work_time_limit=5
            ),
            routing_profile_arn=self.routing_profile.attr_routing_profile_arn,
            username="Admin",
            password="Connect1",
            security_profile_arns=[self.security_profile.attr_security_profile_arn],           
            identity_info=connect.CfnUser.UserIdentityInfoProperty(
                email="admin@example.com",
                first_name="Admin",
                last_name="User"
            ),       
        )

        CfnOutput(self, "ConnectPhoneNumber", 
                  value=phone_number.attr_address,
                  export_name="PhoneNumber")
        
        
        
        
